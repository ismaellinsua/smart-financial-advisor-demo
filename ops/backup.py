"""Encrypted backups of every business database, and a restore drill that proves they work.

    python ops/backup.py --out backups        # take the copies
    python ops/backup.py --verify backups     # restore them into a scratch PostgreSQL and compare
    python ops/backup.py --decrypt FILE.enc   # get a copy back (writes FILE without .enc)
    python ops/backup.py --check              # is everything set up? (connects, takes no copy)
    python ops/backup.py --record backups     # after --verify: note the checked copy in the operator panel
    python ops/backup.py --restore FILE.dump.enc   # full copy into the empty database RESTORE_TARGET_URL
    python ops/backup.py --alert "text"       # email OPERATOR_EMAIL that the night's copy failed

Environment:
    BACKUP_DATABASES   one business per line: «name=postgresql://…» (or DATABASE_URL for a single one)
    BACKUP_PASSPHRASE  encryption passphrase (required: copies are never written unencrypted)
    RESTORE_URL        scratch PostgreSQL for --verify, e.g. postgresql://postgres:pw@localhost:5432/postgres
    RESTORE_TARGET_URL empty database for --restore (an environment variable, so its password stays out of the
                       shell history and the process list)

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
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, UTC
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


NEW_COPY_MIN_LENGTH = 32  # copies are stored outside the database (e.g. CI artifacts): the passphrase is all that protects them


def passphrase(minimum: int = 16) -> str:
    value = os.environ.get("BACKUP_PASSPHRASE", "")
    if len(value) < minimum:
        fail(f"BACKUP_PASSPHRASE debe tener al menos {minimum} caracteres: las copias nunca se guardan sin cifrar y "
             "esa frase es lo único que las protege.")
    return value


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        # libpq may echo the connection target; never print anything that could contain a password.
        detail = re.sub(r"postgres(ql)?://\S+", "postgresql://…", result.stderr.strip())[-600:]
        fail(f"{Path(cmd[0]).name} falló: {detail}")
    return result


def libpq(url: str) -> tuple[str, dict]:
    """The URL without its password, and an environment carrying it in PGPASSWORD: arguments of pg_dump and
    pg_restore are visible to every process on the machine, the environment is not."""
    from urllib.parse import unquote

    parts = urlsplit(url)
    if parts.password is None:
        return url, dict(os.environ)
    netloc = parts.hostname or ""
    if parts.username:
        netloc = f"{parts.username}@{netloc}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit(parts._replace(netloc=netloc)), {**os.environ, "PGPASSWORD": unquote(parts.password)}


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


def read_only(url: str, schema: str | None = None):
    import psycopg
    from psycopg.rows import dict_row

    from core.engines import load_numbers, secure_url

    conn = psycopg.connect(secure_url(url), row_factory=dict_row, options="-c default_transaction_read_only=on",
                           connect_timeout=30)
    load_numbers(conn)  # amounts as the app reads them (NUMERIC → float)
    if schema:
        conn.execute(f'SET search_path TO "{schema}"')  # one business of a shared database
    return conn


def units(name: str, url: str) -> list[tuple[str, str | None]]:
    """What to copy from one database: the whole of it, or, when it serves several businesses, each business's
    schema separately (so each can be restored on its own) plus the operator's directory."""
    from core.tenants import DIRECTORY_SCHEMA

    with read_only(url) as conn:
        shared = conn.execute("SELECT to_regclass(%s) AS t", (f"{DIRECTORY_SCHEMA}.tenants",)).fetchone()["t"]
        if not shared:
            return [(name, None)]
        tenants = conn.execute(f"SELECT code, schema_name FROM {DIRECTORY_SCHEMA}.tenants ORDER BY code").fetchall()
    return [(f"{name}-{t['code']}", t["schema_name"]) for t in tenants] + [(f"{name}-operador", DIRECTORY_SCHEMA)]


def counts_pg(conn) -> dict[str, int]:
    existing = {r["table_name"] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()").fetchall()}
    return {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"] for t in COUNTED if t in existing}


def app_copy(conn, target: Path) -> None:
    """The app's backup format, built from a read-only connection (no migrations run on production)."""
    from core.db import Store
    from core.schema import ALL_TABLES

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
    secret = passphrase(NEW_COPY_MIN_LENGTH)  # older, shorter phrases still open old copies (--decrypt, --verify)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    manifest = {"created_utc": stamp, "businesses": {}}
    from core.tenants import DIRECTORY_SCHEMA

    for base, url in databases().items():
        for name, schema in units(base, url):
            directory_only = schema == DIRECTORY_SCHEMA
            dump, db_file = out / f"{name}-{stamp}.dump", out / f"{name}-{stamp}.db"
            with read_only(url, schema) as conn:
                counts = {} if directory_only else counts_pg(conn)
                server = conn.execute("SHOW server_version_num").fetchone()["server_version_num"]
                if not directory_only:
                    app_copy(conn, db_file)
            only = [f"--schema={schema}"] if schema else []
            source, env = libpq(url)
            run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges", *only, f"--file={dump}",
                 f"--dbname={source}"], env=env)
            files = {}
            for plain in (dump,) if directory_only else (dump, db_file):
                enc = encrypt(plain, secret)
                files[enc.name] = hashlib.sha256(enc.read_bytes()).hexdigest()
            manifest["businesses"][name] = {"counts": counts, "server_version": int(server), "files": files,
                                            "schema": schema}
            print(f"{name}: copia cifrada ({', '.join(f'{k} {v}' for k, v in counts.items()) or 'directorio'})")
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
        schema = info.get("schema")
        with tempfile.TemporaryDirectory() as tmp:
            dump_enc = next(folder / f for f in info["files"] if f.endswith(".dump.enc"))
            db_enc = next((folder / f for f in info["files"] if f.endswith(".db.enc")), None)
            dump = decrypt(dump_enc, secret, Path(tmp) / "copy.dump")
            db_file = decrypt(db_enc, secret, Path(tmp) / "copy.db") if db_enc else None

            scratch = f"drill_{name.replace('-', '_')}"
            with psycopg.connect(restore_url, autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
                admin.execute(f'CREATE DATABASE "{scratch}"')
            target = urlunsplit(urlsplit(restore_url)._replace(path=f"/{scratch}"))
            dbname, env = libpq(target)
            run(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", f"--dbname={dbname}", str(dump)],
                env=env)
            if db_file is None:  # the operator's directory: restoring it without errors is the check
                print(f"{name}: directorio restaurado")
                continue
            with read_only(target, schema) as conn:
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
    manifest["verified_utc"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "")
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Simulacro de restauración correcto.")


def _major(version_num: int) -> int:
    return int(version_num) // 10000


def check() -> None:
    """Everything the night's copy needs, without taking it: secrets, tools, connection and pg_dump's version."""
    passphrase(NEW_COPY_MIN_LENGTH)
    for tool in ("pg_dump", "pg_restore", "openssl"):
        if not shutil.which(tool):
            fail(f"Falta {tool} en este equipo.")
    dump_major = int(re.search(r"(\d+)", run(["pg_dump", "--version"]).stdout).group(1))
    for base, url in databases().items():
        found = units(base, url)
        with read_only(url) as conn:
            server = _major(conn.execute("SHOW server_version_num").fetchone()["server_version_num"])
        if dump_major < server:
            fail(f"{base}: pg_dump {dump_major} no puede copiar PostgreSQL {server}: instala pg_dump {server} o más nuevo.")
        print(f"{base}: conexión correcta, PostgreSQL {server}, {len(found)} copia(s) cada noche")
    print("Configuración de copias correcta.")


def record(folder: Path) -> None:
    """Note a verified night in each shared database's directory, where the operator panel shows it. Only copies that
    passed --verify are recorded: the panel never says «safe» about a copy nobody restored."""
    import psycopg

    from core.engines import secure_url
    from core.tenants import DIRECTORY_SCHEMA

    manifest = json.loads((folder / "manifest.json").read_text())
    if not manifest.get("verified_utc"):
        fail("Estas copias no han pasado el simulacro (--verify): no se anotan.")
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    # Recorded after the upload step: in the workflow a failed external copy stops the run before this.
    offsite = 1 if os.environ.get("BACKUP_S3_BUCKET") else 0
    for base, url in databases().items():
        mine = [info for name, info in manifest["businesses"].items() if name == base or name.startswith(base + "-")]
        files = [f for info in mine for f in info["files"]]
        size = sum((folder / f).stat().st_size for f in files if (folder / f).exists())
        # The backups' role reads only by default; this one transaction may write, and its grants allow one table.
        with psycopg.connect(secure_url(url), autocommit=True, connect_timeout=30) as conn:
            if not conn.execute("SELECT to_regclass(%s)", (f"{DIRECTORY_SCHEMA}.backup_runs",)).fetchone()[0]:
                shared = conn.execute("SELECT to_regclass(%s)", (f"{DIRECTORY_SCHEMA}.tenants",)).fetchone()[0]
                print(f"::warning::{base}: copia verificada, pero la app desplegada aún no tiene dónde anotarla: "
                      "despliega la versión nueva (Render → Manual Deploy) para verla en el panel de operador."
                      if shared else f"{base}: base de un solo negocio, sin panel de operador donde anotarla")
                continue
            with conn.transaction():
                conn.execute("SET TRANSACTION READ WRITE")
                conn.execute(f"INSERT INTO {DIRECTORY_SCHEMA}.backup_runs(finished_at, copies, size_bytes, detail, "
                             "offsite) VALUES (%s, %s, %s, %s, %s)",
                             (manifest["verified_utc"], len(files), size, run_url, offsite))
        print(f"{base}: copia verificada anotada ({len(files)} archivos)")


def restore(path: Path) -> None:
    """A full copy (…dump.enc) into an EMPTY database: never over data that might be newer than the copy."""
    import psycopg

    from core.engines import secure_url

    if not path.name.endswith(".dump.enc"):
        fail("Para restaurar todo se usa la copia completa (…dump.enc). La copia …db.enc se carga desde la app.")
    target = os.environ.get("RESTORE_TARGET_URL") or fail("Define RESTORE_TARGET_URL: la base vacía de destino.")
    secret = passphrase()
    with psycopg.connect(secure_url(target), connect_timeout=30) as conn:
        tables = conn.execute("SELECT COUNT(*) FROM information_schema.tables "
                              "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')").fetchone()[0]
    if tables:
        fail(f"La base de destino no está vacía ({tables} tablas). Crea una nueva (en Neon: «Branches → New» o una "
             "base nueva) y apunta RESTORE_TARGET_URL a ella; nunca se restaura encima de datos.")
    with tempfile.TemporaryDirectory() as tmp:
        dump = decrypt(path, secret, Path(tmp) / "copy.dump")
        dbname, env = libpq(secure_url(target))
        run(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", f"--dbname={dbname}", str(dump)],
            env=env)
    print(f"Restaurado {path.name} en la base de destino. Compruébala y, si es correcta, apunta DATABASE_URL a ella.")


def alert(text: str) -> None:
    """Email the operator that the night's copy failed (besides GitHub's own email to the repository owner)."""
    to = os.environ.get("OPERATOR_EMAIL", "")
    from core.mailer import Mailer

    mailer = Mailer.from_settings()
    if not to or mailer is None:
        print("Aviso por email sin configurar (OPERATOR_EMAIL y SMTP_*): solo avisa GitHub.")
        return
    mailer.send(to, "NirKanA: la copia de seguridad de esta noche ha fallado",
                f"{text}\n\nMientras no se arregle, no hay copia nueva de los negocios. Revisa el registro de la "
                "ejecución en GitHub (Actions → Copias de seguridad) y vuelve a lanzarla con «Run workflow».")
    print("Aviso enviado.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, help="carpeta donde dejar las copias cifradas")
    group.add_argument("--verify", type=Path, help="carpeta con copias y manifest.json para el simulacro")
    group.add_argument("--decrypt", type=Path, help="descifrar un archivo .enc")
    group.add_argument("--check", action="store_true", help="comprobar la configuración sin hacer copias")
    group.add_argument("--record", type=Path, help="anotar en el panel del operador unas copias ya verificadas")
    group.add_argument("--restore", type=Path, help="restaurar una copia …dump.enc en la base vacía RESTORE_TARGET_URL")
    group.add_argument("--alert", help="avisar por email a OPERATOR_EMAIL de que la copia ha fallado")
    args = parser.parse_args()
    if args.out:
        take(args.out)
    elif args.verify:
        verify(args.verify)
    elif args.check:
        check()
    elif args.record:
        record(args.record)
    elif args.restore:
        restore(args.restore)
    elif args.alert:
        alert(args.alert)
    else:
        if args.decrypt.suffix != ".enc":
            fail("El archivo debe terminar en .enc")
        out = decrypt(args.decrypt, passphrase(), args.decrypt.with_suffix(""))
        print(f"Descifrado: {out}")


if __name__ == "__main__":
    main()
