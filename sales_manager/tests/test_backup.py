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


def _shared_source(name: str):
    """A database serving two businesses, one of them with demo sales and an account."""
    import psycopg

    from core.tenants import Directory

    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {name}")
    source = PG_URL.rsplit("/", 1)[0] + f"/{name}"
    directory = Directory(source)
    directory.create("cafe-aurora", "Café Aurora")
    store = directory.store("cafe-aurora")
    store.load_preset("restaurant")
    store.create_user("Ana", "ana", "admin", "Segura2026!")
    store.close()
    return source, directory


def _backup_role(source: str) -> str:
    """The read-only role of ops/deploy/roles.sql, on this database: its URL."""
    import psycopg

    with psycopg.connect(source, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'nirkana_backup'").fetchone():
            conn.execute("CREATE ROLE nirkana_backup LOGIN")
        conn.execute("ALTER ROLE nirkana_backup PASSWORD 'copias-de-prueba'")
        conn.execute("ALTER ROLE nirkana_backup SET default_transaction_read_only = on")
        for schema in [r[0] for r in conn.execute("SELECT nspname FROM pg_namespace WHERE nspname = 'public' "
                                                  "OR nspname = 'nirkana_operador' OR nspname LIKE 'n\\_%'")]:
            conn.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO nirkana_backup')
            conn.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO nirkana_backup')
            conn.execute(f'GRANT SELECT ON ALL SEQUENCES IN SCHEMA "{schema}" TO nirkana_backup')
    parts = source.split("://", 1)[1].split("@", 1)[1]
    return f"postgresql://nirkana_backup:copias-de-prueba@{parts}"


def test_check_says_what_is_missing_before_the_night_comes(tmp_path):
    source, _ = _shared_source("backup_check")
    env = {**os.environ, "BACKUP_DATABASES": f"nube={source}",
           "BACKUP_PASSPHRASE": "frase-de-prueba-muy-larga-y-segura-2026"}
    ok = _run(["--check"], env)
    assert ok.returncode == 0, ok.stderr
    assert "nube: conexión correcta" in ok.stdout and "2 copia(s) cada noche" in ok.stdout  # business + directory
    assert "correcta" in ok.stdout.splitlines()[-1]

    short = _run(["--check"], {**env, "BACKUP_PASSPHRASE": "corta"})
    assert short.returncode != 0 and "32 caracteres" in short.stderr
    unreachable = _run(["--check"], {**env, "BACKUP_DATABASES": "nube=postgresql://u:secreta-123@127.0.0.1:1/x"})
    assert unreachable.returncode != 0 and "secreta-123" not in unreachable.stdout + unreachable.stderr
    assert _run(["--check"], {**env, "BACKUP_DATABASES": "sin formato"}).returncode != 0


def test_only_a_verified_night_reaches_the_operator_panel(tmp_path):
    from core.tenants import Directory

    source, directory = _shared_source("backup_record")
    level, message = directory.backup_status()
    assert level == "falta" and "ninguna copia" in message  # a database that was never copied says so

    readonly = _backup_role(source)
    Directory(source)  # the app grants the backups' role its one table when it starts
    env = {**os.environ, "BACKUP_DATABASES": f"nube={readonly}", "RESTORE_URL": PG_URL,
           "BACKUP_PASSPHRASE": "frase-de-prueba-muy-larga-y-segura-2026", "GITHUB_RUN_ID": "77",
           "GITHUB_REPOSITORY": "dueno/nirkana"}
    out = tmp_path / "copias"
    assert _run(["--out", str(out)], env).returncode == 0
    unverified = _run(["--record", str(out)], env)
    assert unverified.returncode != 0 and "simulacro" in unverified.stderr
    assert directory.last_backup() is None

    assert _run(["--verify", str(out)], env).returncode == 0
    noted = _run(["--record", str(out)], env)
    assert noted.returncode == 0, noted.stderr
    last = directory.last_backup()
    assert last["copies"] == 3 and last["size_bytes"] > 0 and last["detail"].endswith("/dueno/nirkana/actions/runs/77")
    level, message = directory.backup_status()
    assert level == "aviso" and "hace menos de una hora" in message and "3 copias cifradas" in message
    assert "copia externa" in message  # only GitHub's artifacts: 30 days, one provider
    assert _run(["--record", str(out)], {**env, "BACKUP_S3_BUCKET": "copias"}).returncode == 0
    assert directory.backup_status()[0] == "ok"

    import psycopg

    with psycopg.connect(readonly) as conn:  # still read-only everywhere else
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("DELETE FROM nirkana_operador.backup_runs")


def test_a_missed_night_shows_red(tmp_path):
    from datetime import timedelta

    from core.billing import utc_now

    _, directory = _shared_source("backup_age")
    with directory._connect() as conn:
        conn.execute("INSERT INTO nirkana_operador.backup_runs(finished_at, copies, size_bytes) VALUES (%s, 3, 1)",
                     ((utc_now() - timedelta(hours=30)).isoformat(timespec="seconds"),))
    level, message = directory.backup_status()
    assert level == "falta" and "hace 30 h" in message and "falta" in message
    assert directory.backup_status(utc_now() - timedelta(hours=10))[0] != "falta"


def test_restore_goes_only_into_an_empty_database(tmp_path):
    import psycopg

    source, _ = _shared_source("backup_restore_src")
    env = {**os.environ, "BACKUP_DATABASES": f"nube={source}",
           "BACKUP_PASSPHRASE": "frase-de-prueba-muy-larga-y-segura-2026"}
    out = tmp_path / "copias"
    assert _run(["--out", str(out)], env).returncode == 0
    dump = next(out.glob("nube-cafe-aurora-*.dump.enc"))

    with psycopg.connect(PG_URL, autocommit=True) as admin:
        admin.execute("DROP DATABASE IF EXISTS backup_restore_dst WITH (FORCE)")
        admin.execute("CREATE DATABASE backup_restore_dst")
    target = PG_URL.rsplit("/", 1)[0] + "/backup_restore_dst"
    restored = _run(["--restore", str(dump)], {**env, "RESTORE_TARGET_URL": target})
    assert restored.returncode == 0, restored.stderr
    with psycopg.connect(target) as conn:
        assert conn.execute('SELECT COUNT(*) FROM "n_cafe_aurora".sales').fetchone()[0] > 0

    again = _run(["--restore", str(dump)], {**env, "RESTORE_TARGET_URL": target})
    assert again.returncode != 0 and "no está vacía" in again.stderr  # never over data that may be newer
    app_copy = next(out.glob("*.db.enc"))
    assert _run(["--restore", str(app_copy)], {**env, "RESTORE_TARGET_URL": target}).returncode != 0
    assert _run(["--restore", str(dump)], env).returncode != 0  # no target given


def test_a_failed_night_is_emailed_when_smtp_is_set(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("backup_script", SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    sent = []

    class FakeMailer:
        def send(self, to, subject, text):
            sent.append((to, subject, text))

    import core.mailer

    monkeypatch.setattr(core.mailer.Mailer, "from_settings", classmethod(lambda cls, get=None: FakeMailer()))
    monkeypatch.setenv("OPERATOR_EMAIL", "operador@example.com")
    script.alert("Ejecución https://github.com/x/y/actions/runs/1")
    assert sent and sent[0][0] == "operador@example.com" and "ha fallado" in sent[0][1]
    assert "actions/runs/1" in sent[0][2]
    monkeypatch.delenv("OPERATOR_EMAIL")
    script.alert("otra")
    assert len(sent) == 1  # without OPERATOR_EMAIL only GitHub's own email goes out


def test_passwords_never_reach_the_command_line():
    import importlib.util

    spec = importlib.util.spec_from_file_location("backup_script2", SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    url, env = script.libpq("postgresql://usuario:cl%40ve-secreta@db.example.com:5432/neondb?sslmode=require")
    assert url == "postgresql://usuario@db.example.com:5432/neondb?sslmode=require"
    assert env["PGPASSWORD"] == "cl@ve-secreta"
