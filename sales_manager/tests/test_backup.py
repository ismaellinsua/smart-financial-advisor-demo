"""The backup script: encrypted copies of a real PostgreSQL database and a restore drill that compares them."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PG_URL
from core.db import Store

SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "backup.py"
pytestmark = pytest.mark.skipif(not PG_URL or not shutil.which("pg_dump") or not shutil.which("openssl"),
                                reason="needs TEST_DATABASE_URL, pg_dump and openssl")


def _run(args, env):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)


def test_backup_and_restore_drill(tmp_path):
    import psycopg

    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute("DROP DATABASE IF EXISTS backup_source")
        admin.execute("CREATE DATABASE backup_source")
    source = PG_URL.rsplit("/", 1)[0] + "/backup_source"
    store = Store(source)
    store.load_preset("services")
    store.create_user("Dueña", "duena", "admin", "Dueña2026!")
    sales = len(store.sales())
    store.close()

    env = {**os.environ, "BACKUP_DATABASES": f"peluqueria={source}", "BACKUP_PASSPHRASE": "frase-de-prueba-muy-larga-y-segura-2026",
           "RESTORE_URL": PG_URL}
    out = tmp_path / "copias"
    taken = _run(["--out", str(out)], env)
    assert taken.returncode == 0, taken.stderr
    assert f"sales {sales}" in taken.stdout and "postgresql://" not in taken.stdout + taken.stderr
    assert sorted(p.suffix for p in out.iterdir()) == [".enc", ".enc", ".json"]  # nothing left unencrypted

    drill = _run(["--verify", str(out)], env)
    assert drill.returncode == 0, drill.stderr
    assert "1 cuentas" in drill.stdout and "correcto" in drill.stdout

    enc = next(out.glob("*.db.enc"))
    data = bytearray(enc.read_bytes())
    data[200] ^= 0xFF
    enc.write_bytes(bytes(data))
    assert _run(["--verify", str(out)], env).returncode != 0  # a damaged copy is reported

    assert _run(["--out", str(tmp_path / "x")], {**env, "BACKUP_PASSPHRASE": "corta"}).returncode != 0
    wrong = _run(["--decrypt", str(next(out.glob("*.dump.enc")))], {**env, "BACKUP_PASSPHRASE": "otra-frase-larga-2026"})
    assert wrong.returncode != 0 and "frase incorrecta" in wrong.stderr


def test_shared_database_is_copied_business_by_business(tmp_path):
    import psycopg

    from core.tenants import Directory

    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute("DROP DATABASE IF EXISTS backup_shared WITH (FORCE)")
        admin.execute("CREATE DATABASE backup_shared")
    source = PG_URL.rsplit("/", 1)[0] + "/backup_shared"
    directory = Directory(source)
    directory.create("cafe-aurora", "Café Aurora")
    directory.create("tienda-sol", "Tienda Sol")
    aurora = directory.store("cafe-aurora")
    aurora.load_preset("restaurant")
    aurora.create_user("Ana", "ana", "admin", "Segura2026!")
    sales = len(aurora.sales())
    aurora.close()

    env = {**os.environ, "BACKUP_DATABASES": f"nube={source}", "BACKUP_PASSPHRASE": "frase-de-prueba-muy-larga-y-segura-2026",
           "RESTORE_URL": PG_URL}
    out = tmp_path / "copias"
    taken = _run(["--out", str(out)], env)
    assert taken.returncode == 0, taken.stderr
    assert "nube-cafe-aurora: copia cifrada (products" in taken.stdout and f"sales {sales}" in taken.stdout
    assert "nube-tienda-sol: copia cifrada" in taken.stdout and "nube-operador: copia cifrada (directorio)" in taken.stdout
    names = {p.name.split("-2")[0] for p in out.glob("*.enc")}
    assert names == {"nube-cafe-aurora", "nube-tienda-sol", "nube-operador"}

    drill = _run(["--verify", str(out)], env)
    assert drill.returncode == 0, drill.stderr
    assert "nube-cafe-aurora: restaurada y comprobada (1 cuentas" in drill.stdout
    assert "nube-tienda-sol: restaurada y comprobada (0 cuentas" in drill.stdout and "correcto" in drill.stdout
    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute("DROP DATABASE IF EXISTS backup_shared WITH (FORCE)")
