import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import Store  # noqa: E402

# Set TEST_DATABASE_URL (e.g. postgresql://user:pass@localhost:5432/db) to also run every storage test on PostgreSQL.
PG_URL = os.environ.get("TEST_DATABASE_URL")
BACKENDS = ["sqlite", pytest.param("postgres", marks=pytest.mark.skipif(not PG_URL, reason="TEST_DATABASE_URL not set"))]


class Targets:
    """Creates isolated databases: SQLite files, or one fresh PostgreSQL schema each."""

    def __init__(self, backend, tmp_path):
        self.backend, self.tmp_path, self.schemas = backend, Path(tmp_path), []
        self.roles = {}  # target → the role that may only touch its schema, as in production

    def new(self) -> str:
        if self.backend == "sqlite":
            return str(self.tmp_path / f"{uuid.uuid4().hex}.db")
        import psycopg

        from core.engines import create_tenant_role

        schema = f"t_{uuid.uuid4().hex[:12]}"
        with psycopg.connect(PG_URL, autocommit=True) as conn:
            conn.execute(f"CREATE SCHEMA {schema}")
            role = create_tenant_role(conn, schema)
        self.schemas.append(schema)
        sep = "&" if "?" in PG_URL else "?"
        target = f"{PG_URL}{sep}options=-csearch_path%3D{schema}"
        self.roles[target] = role
        return target

    def cleanup(self) -> None:
        if self.schemas:
            import psycopg

            with psycopg.connect(PG_URL, autocommit=True) as conn:
                for schema in self.schemas:
                    conn.execute(f"DROP SCHEMA {schema} CASCADE")
                for role in self.roles.values():
                    conn.execute(f'DROP OWNED BY "{role}"')
                    conn.execute(f'DROP ROLE IF EXISTS "{role}"')


@pytest.fixture(params=BACKENDS)
def make_store(request, tmp_path):
    targets = Targets(request.param, tmp_path)
    stores = []

    def factory(target=None, owner=False):
        """`owner`: as the schema's owner, for tests that rebuild an old database by hand (DDL)."""
        target = target or targets.new()
        role = None if owner else targets.roles.get(target)
        s = Store(target, role=role)  # every other PostgreSQL test runs as a business's own role
        stores.append(s)
        return s

    factory.targets = targets
    yield factory
    for s in stores:
        s.close()
    targets.cleanup()


@pytest.fixture(scope="module", params=BACKENDS)
def module_targets(request, tmp_path_factory):
    targets = Targets(request.param, tmp_path_factory.mktemp("db"))
    yield targets
    targets.cleanup()


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """Production hashing is deliberately slow; tests use fewer rounds of the same algorithm."""
    import core.security

    monkeypatch.setattr(core.security, "PBKDF2_ITERATIONS", 1_000)
