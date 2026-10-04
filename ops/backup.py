"""Encrypted backups of every business database, and a restore drill that proves they work.

    python ops/backup.py --out backups        # take the copies
    python ops/backup.py --verify backups     # restore them into a scratch PostgreSQL and compare
    python ops/backup.py --decrypt FILE.enc   # get a copy back (writes FILE without .enc)

Environment:
    BACKUP_DATABASES   one business per line: «name=postgresql://…» (or DATABASE_URL for a single one)
    BACKUP_PASSPHRASE  encryption passphrase (required: copies are never written unencrypted)
    RESTORE_URL        scratch PostgreSQL for --verify, e.g. postgresql://postgres:pw@localhost:5432/postgres

Each business gets two files, both AES-256 encrypted with openssl:
    NAME-DATE.dump.enc  full pg_dump (accounts and activity log included): disaster recovery with pg_restore
    NAME-DATE.db.enc    the app's own copy (Configuración → Restaurar), without accounts
The production database is only read, never migrated or written.
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sales_manager"))

COUNTED = ["products", "customers", "sales", "invoices", "refunds", "credit_notes", "cash_closings", "billing_records"]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def databases() -> dict[str, str]:
    raw = os.environ.get("BACKUP_DATABASES", "").strip()
    if not raw and os.environ.get("DATABASE_URL"):
        raw = f"negocio={os.environ['DATABASE_URL']}"
    found = {}
    for line in filter(None, (l.strip() for l in raw.splitlines())):
        name, sep, url = line.partition("=")
        name = name.strip().lower()
        if not sep or not NAME_RE.fullmatch(name) or not url.strip().startswith(("postgresql://", "postgres://")):
            fail("BACKUP_DATABASES: cada línea debe ser «nombre=postgresql://…» (nombre en minúsculas, sin espacios).")
        found[name] = url.strip()
    if not found:
        fail("No hay bases de datos: define BACKUP_DATABASES.")
    return found


def passphrase() -> str:
    value = os.environ.get("BACKUP_PASSPHRASE", "")
    if len(value) < 16:
        fail("BACKUP_PASSPHRASE debe tener al menos 16 caracteres: las copias nunca se guardan sin cifrar.")
    return value


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        # libpq may echo the connection target; never print anything that could contain a password.
        detail = re.sub(r"postgres(ql)?://\S+", "postgresql://…", result.stderr.strip())[-600:]
        fail(f"{Path(cmd[0]).name} falló: {detail}")
    return result


def encrypt(path: Path, secret: str) -> Path:
    out = path.with_name(path.name + ".enc")
    run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "600000", "-salt", "-in", str(path), "-out", str(out),
         "-pass", "env:BACKUP_PASSPHRASE"], env={**os.environ, "BACKUP_PASSPHRASE": secret})
    path.unlink()
    return out


def decrypt(path: Path, secret: str, out: Path) -> Path:
    result = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "600000", "-in", str(path),
                             "-out", str(out), "-pass", "env:BACKUP_PASSPHRASE"],
                            capture_output=True, text=True, env={**os.environ, "BACKUP_PASSPHRASE": secret})
    if result.returncode != 0:
        out.unlink(missing_ok=True)
        fail(f"No se pudo descifrar {path.name}: frase incorrecta o archivo dañado.")
    return out


def read_only(url: str):
    import psycopg
    from psycopg.rows import dict_row

    from core.db import _secure_url

    return psycopg.connect(_secure_url(url), row_factory=dict_row, options="-c default_transaction_read_only=on",
                           connect_timeout=30)


def counts_pg(conn) -> dict[str, int]:
    existing = {r["table_name"] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()").fetchall()}
    return {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"] for t in COUNTED if t in existing}


def app_copy(conn, target: Path) -> None:
    """The app's backup format, built from a read-only connection (no migrations run on production)."""
    from core.db import ALL_TABLES, Store

    existing = {r["table_name"] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()").fetchall()}
    data = {}
    for table in ALL_TABLES:
        if table in existing:
            order = "key" if table == "settings" else "id"
            data[table] = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
    copy = Store(target)
    try:
        with copy.db.tx() as cur:
            copy._replace(cur, data)
    finally:
        copy.close()


def take(out: Path) -> None:
    secret = passphrase()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    manifest = {"created_utc": stamp, "businesses": {}}
    for name, url in databases().items():
        dump, db_file = out / f"{name}-{stamp}.dump", out / f"{name}-{stamp}.db"
        with read_only(url) as conn:
            counts = counts_pg(conn)
            server = conn.execute("SHOW server_version_num").fetchone()["server_version_num"]
            app_copy(conn, db_file)
        run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges", f"--file={dump}", f"--dbname={url}"])
        files = {}
        for plain in (dump, db_file):
            enc = encrypt(plain, secret)
            files[enc.name] = hashlib.sha256(enc.read_bytes()).hexdigest()
        manifest["businesses"][name] = {"counts": counts, "server_version": int(server), "files": files}
        print(f"{name}: copia cifrada ({', '.join(f'{k} {v}' for k, v in counts.items())})")
    # Kept next to the copies for --verify; counts are not secret, but it is not uploaded with them.
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))


def verify(folder: Path) -> None:
    """Restore every copy and compare it with what production had when it was taken."""
    import psycopg

    secret = passphrase()
    restore_url = os.environ.get("RESTORE_URL") or fail("Define RESTORE_URL (PostgreSQL de pruebas).")
    manifest = json.loads((folder / "manifest.json").read_text())
    problems = []
    for name, info in manifest["businesses"].items():
        for file, digest in info["files"].items():
            if hashlib.sha256((folder / file).read_bytes()).hexdigest() != digest:
                problems.append(f"{name}: {file} no coincide con su huella")
        with tempfile.TemporaryDirectory() as tmp:
            dump_enc = next(folder / f for f in info["files"] if f.endswith(".dump.enc"))
            db_enc = next(folder / f for f in info["files"] if f.endswith(".db.enc"))
            dump = decrypt(dump_enc, secret, Path(tmp) / "copy.dump")
            db_file = decrypt(db_enc, secret, Path(tmp) / "copy.db")

            scratch = f"drill_{name.replace('-', '_')}"
            with psycopg.connect(restore_url, autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
                admin.execute(f'CREATE DATABASE "{scratch}"')
            target = urlunsplit(urlsplit(restore_url)._replace(path=f"/{scratch}"))
            run(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", f"--dbname={target}", str(dump)])
            with read_only(target) as conn:
                restored = counts_pg(conn)
                users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            if restored != info["counts"]:
                problems.append(f"{name}: la copia completa no coincide ({restored} ≠ {info['counts']})")

            check = sqlite3.connect(db_file)
            try:
                ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                app_counts = {t: check.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in info["counts"]}
            finally:
                check.close()
            if not ok or app_counts != info["counts"]:
                problems.append(f"{name}: la copia de la app no coincide ({app_counts} ≠ {info['counts']})")
            print(f"{name}: restaurada y comprobada ({users} cuentas, "
                  f"{', '.join(f'{k} {v}' for k, v in restored.items())})")
    if problems:
        fail("; ".join(problems))
    print("Simulacro de restauración correcto.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, help="carpeta donde dejar las copias cifradas")
    group.add_argument("--verify", type=Path, help="carpeta con copias y manifest.json para el simulacro")
    group.add_argument("--decrypt", type=Path, help="descifrar un archivo .enc")
    args = parser.parse_args()
    if args.out:
        take(args.out)
    elif args.verify:
        verify(args.verify)
    else:
        if args.decrypt.suffix != ".enc":
            fail("El archivo debe terminar en .enc")
        out = decrypt(args.decrypt, passphrase(), args.decrypt.with_suffix(""))
        print(f"Descifrado: {out}")


if __name__ == "__main__":
    main()
