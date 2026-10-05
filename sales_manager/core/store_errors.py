"""Errors the app hit while someone was using it, so the operator hears about them before the customer calls.

Only the kind of error and the line of NirKanA's own code where it happened are kept, never the error message: it
can contain customers' or sales data. Each error gets a short reference the person can quote. Mixed into `Store`.
"""

import secrets
import traceback
from datetime import timedelta
from pathlib import Path

import pandas as pd

from . import clock

APP_ROOT = Path(__file__).resolve().parent.parent


def where_in_app(exc: BaseException) -> str:
    """The deepest frame inside the app's own code, e.g. 'ui/pages.py:812 point_of_sale'."""
    found = ""
    for frame in traceback.extract_tb(exc.__traceback__):
        path = Path(frame.filename)
        if APP_ROOT in path.parents:
            found = f"{path.relative_to(APP_ROOT)}:{frame.lineno} {frame.name}"
    return found


class ErrorsMixin:
    def record_error(self, exc: BaseException, page: str = "", username: str = "") -> str:
        ref = secrets.token_hex(3).upper()
        with self.db.tx() as cur:
            cur.execute("INSERT INTO app_errors(happened_at, ref, page, username, kind, where_) VALUES (?, ?, ?, ?, ?, ?)",
                        (clock.now().isoformat(timespec="seconds"), ref, str(page)[:80], str(username)[:30],
                         type(exc).__name__[:80], where_in_app(exc)[:200]))
        return ref

    def recent_errors(self, days: int = 7) -> pd.DataFrame:
        since = (clock.now() - timedelta(days=days)).isoformat(timespec="seconds")
        df = self._frame("SELECT happened_at, ref, page, username, kind, where_ FROM app_errors WHERE happened_at >= ? "
                         "ORDER BY id DESC LIMIT 200", (since,))
        df["happened_at"] = pd.to_datetime(df["happened_at"])
        return df
