"""Bulk copy between databases, downloadable backups and restoring them. Mixed into `Store`."""

import sqlite3
import tempfile
from pathlib import Path

from .engines import _Cursor
from .schema import ALL_TABLES, CORE_TABLES
from .security import is_safe_identifier


MAX_RESTORED_TEXT = 20_000  # longest text a restored copy may hold (the app's own limits are far lower)


class BackupMixin:
    # ------------------------------------------------------- bulk copy & backups
    def _export(self, tables: list[str]) -> dict[str, list[dict]]:
        with self.db.tx() as cur:
            return {
                t: cur.execute(f"SELECT * FROM {t} ORDER BY {'key' if t == 'settings' else 'id'}").fetchall()
                for t in tables
            }

    def _replace(self, cur: _Cursor, data: dict[str, list[dict]]) -> None:
        """Replace the contents of the given tables, keeping ids. Callers pass all of DATA_TABLES together."""
        tables = [t for t in ALL_TABLES if t in data]
        for table in reversed(tables):
            cur.execute(f"DELETE FROM {table}")
        cur.execute("DELETE FROM counters")  # numbering restarts from the data that is loaded
        cur.execute("DELETE FROM pos_carts")  # tickets in progress point to products that are being replaced
        self.db.before_reload(cur, tables)
        for table in tables:
            rows = data[table]
            if rows:
                # Column names come from a file the user uploaded: keep only real, well-formed columns.
                known = self.db.columns(cur, table)
                columns = [col for col in rows[0] if col in known and is_safe_identifier(col)]
                cur.executemany(
                    f"INSERT INTO {table}({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                    ([r[c] for c in columns] for r in rows),
                )
        self.db.after_reload(cur, tables)
        self._backfill_payments(cur)

    REQUIRED_TABLES = CORE_TABLES

    def backup_bytes(self) -> bytes:
        """The whole database as a SQLite file, whichever engine holds it."""
        data = self._export(ALL_TABLES)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.db"
            copy = type(self)(path)
            try:
                with copy.db.tx() as cur:
                    copy._replace(cur, data)
            finally:
                copy.close()
            return path.read_bytes()

    def restore(self, data: bytes) -> None:
        """Replace all data with a backup produced by `backup_bytes`. Validates it before touching anything.

        Only into a demonstration or a business without sales yet (e.g. moving to a new database): restoring
        over real records would destroy everything issued after the copy was made.
        """
        self._guard_replace()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "restore.db"
            path.write_bytes(data)
            try:
                check = sqlite3.connect(path)
                try:
                    tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                    ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                finally:
                    check.close()
            except sqlite3.DatabaseError as exc:
                raise ValueError("El archivo no es una copia de seguridad válida.") from exc
            if not ok or not self.REQUIRED_TABLES <= tables:
                raise ValueError("El archivo no es una copia de seguridad de este gestor o está dañado.")
            source = type(self)(path)  # also upgrades backups made by older versions
            try:
                rows = source._export(ALL_TABLES)
            finally:
                source.close()
        # A copy edited by hand must not bring texts the app would never have accepted.
        for table, table_rows in rows.items():
            for row in table_rows:
                if any(isinstance(v, str) and len(v) > MAX_RESTORED_TEXT for v in row.values()):
                    raise ValueError(f"La copia tiene textos demasiado largos en «{table}»: no parece una copia de "
                                     "esta app sin modificar.")
        with self.db.tx() as cur:
            self._replace(cur, rows)
            self._insert_default_settings(cur)
