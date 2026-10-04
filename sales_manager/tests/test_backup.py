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

    env = {**os.environ, "BACKUP_DATABASES": f"peluqueria={source}", "BACKUP_PASSPHRASE": "frase-de-prueba-muy-larga",
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
