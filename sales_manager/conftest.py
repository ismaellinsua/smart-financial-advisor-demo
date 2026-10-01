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

    def new(self) -> str:
        if self.backend == "sqlite":
            return str(self.tmp_path / f"{uuid.uuid4().hex}.db")
        import psycopg

        schema = f"t_{uuid.uuid4().hex[:12]}"
        with psycopg.connect(PG_URL, autocommit=True) as conn:
            conn.execute(f"CREATE SCHEMA {schema}")
        self.schemas.append(schema)
        sep = "&" if "?" in PG_URL else "?"
        return f"{PG_URL}{sep}options=-csearch_path%3D{schema}"

    def cleanup(self) -> None:
        if self.schemas:
            import psycopg

            with psycopg.connect(PG_URL, autocommit=True) as conn:
                for schema in self.schemas:
                    conn.execute(f"DROP SCHEMA {schema} CASCADE")


@pytest.fixture(params=BACKENDS)
def make_store(request, tmp_path):
    targets = Targets(request.param, tmp_path)
    stores = []

    def factory(target=None):
        s = Store(target or targets.new())
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
