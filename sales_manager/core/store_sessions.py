"""Remembered sign-ins and the ticket in progress, so reloading the page or the phone discarding the tab neither
signs staff out nor loses the sale being rung up. Mixed into `Store`.

The browser keeps only a random token; the database keeps its SHA-256, so a copy of the database cannot be used to
sign in. A session ends after the business's idle time, on logout, and when the person's PIN changes or their
account is deactivated.
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta

from . import clock

TOUCH_EVERY = timedelta(minutes=1)  # last_seen is written at most once a minute, not on every click


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SessionsMixin:
    def create_session(self, user_id: int, user_agent: str = "") -> str:
        token = secrets.token_urlsafe(32)
        stamp = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            cur.execute("INSERT INTO sessions(user_id, token_hash, created_at, last_seen, user_agent) "
                        "VALUES (?, ?, ?, ?, ?)", (int(user_id), _digest(token), stamp, stamp, str(user_agent)[:200]))
        return token

    def resume_session(self, token: str, idle_minutes: int) -> dict | None:
        """The active user behind a remembered sign-in, or None if it ended, expired or is unknown."""
        if not isinstance(token, str) or not token or len(token) > 100:
            return None
        now = clock.now()
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT s.id, s.last_seen, u.id AS user_id, u.username, u.name, u.role FROM sessions s "
                "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.ended_at = '' AND u.active = 1",
                (_digest(token),)).fetchone()
            if row is None:
                return None
            seen = datetime.fromisoformat(row["last_seen"])
            if now - seen > timedelta(minutes=max(5, int(idle_minutes))):
                cur.execute("UPDATE sessions SET ended_at = ? WHERE id = ?",
                            (now.isoformat(timespec="seconds"), row["id"]))
                return None
            if now - seen >= TOUCH_EVERY:
                cur.execute("UPDATE sessions SET last_seen = ? WHERE id = ?",
                            (now.isoformat(timespec="seconds"), row["id"]))
        return {"id": row["user_id"], "username": row["username"], "name": row["name"], "role": row["role"]}

    def end_session(self, token: str) -> None:
        if isinstance(token, str) and token:
            with self.db.tx() as cur:
                cur.execute("UPDATE sessions SET ended_at = ? WHERE token_hash = ? AND ended_at = ''",
                            (clock.now().isoformat(timespec="seconds"), _digest(token)))

    @staticmethod
    def _end_user_sessions(cur, user_id: int) -> None:
        cur.execute("UPDATE sessions SET ended_at = ? WHERE user_id = ? AND ended_at = ''",
                    (clock.now().isoformat(timespec="seconds"), int(user_id)))

    # ------------------------------------------------------------ ticket in progress
    def saved_cart(self, user_id: int) -> dict[int, int]:
        with self.db.tx() as cur:
            row = cur.execute("SELECT cart FROM pos_carts WHERE user_id = ?", (int(user_id),)).fetchone()
        try:
            return {int(k): int(v) for k, v in json.loads(row["cart"]).items() if int(v) > 0} if row else {}
        except (ValueError, TypeError, AttributeError):
            return {}

    def save_cart(self, user_id: int, cart: dict) -> None:
        payload = json.dumps({str(int(k)): int(v) for k, v in cart.items() if int(v) > 0})
        with self.db.tx() as cur:
            cur.execute("INSERT INTO pos_carts(user_id, cart, updated_at) VALUES (?, ?, ?) ON CONFLICT(user_id) "
                        "DO UPDATE SET cart = excluded.cart, updated_at = excluded.updated_at",
                        (int(user_id), payload, clock.now().isoformat(timespec="seconds")))
