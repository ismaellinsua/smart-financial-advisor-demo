"""Remembered sign-ins and the ticket in progress, so reloading the page or the phone discarding the tab neither
signs staff out nor loses the sale being rung up. Mixed into `Store`.

The browser keeps only a random token; the database keeps its SHA-256, so a copy of the database cannot be used to
sign in. A session ends after the business's idle time, after SESSION_MAX_AGE whatever the use, on logout, and when
the person's PIN changes or their account is deactivated. Inside the container the cookie is HttpOnly (written by
ops/deploy/sessions.py); elsewhere the page writes it. Either way, a token copied out of the browser is refused on
another kind of browser.
"""

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta

from . import clock
from .security import check_secret_strength, hash_secret, verify_secret

TOUCH_EVERY = timedelta(minutes=1)  # last_seen is written at most once a minute, not on every click
SESSION_MAX_AGE = timedelta(days=7)  # a remembered sign-in never outlives this, however often it is used
RESET_VALID = timedelta(minutes=15)
RESET_MAX_ATTEMPTS = 5
RESET_MAX_PER_HOUR = 3
RESET_MAX_PER_DAY = 6  # with 8-digit codes: at most 30 guesses a day, about one chance in 9,000 in a whole year
RESET_DIGITS = 8


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def browser_family(user_agent: str) -> str:
    """The browser and system without version numbers, so automatic browser updates keep the session."""
    return re.sub(r"[\d._]+", "", str(user_agent or "")[:200]).strip()


class SessionsMixin:
    def create_session(self, user_id: int, user_agent: str = "") -> str:
        token = secrets.token_urlsafe(32)
        stamp = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            cur.execute("INSERT INTO sessions(user_id, token_hash, created_at, last_seen, user_agent) "
                        "VALUES (?, ?, ?, ?, ?)", (int(user_id), _digest(token), stamp, stamp, str(user_agent)[:200]))
        return token

    def resume_session(self, token: str, idle_minutes: int, user_agent: str | None = None) -> dict | None:
        """The active user behind a remembered sign-in, or None if it ended, expired, is unknown or comes from
        another kind of browser than the one that signed in (an unknown `user_agent` skips that check)."""
        if not isinstance(token, str) or not token or len(token) > 100:
            return None
        now = clock.now()
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT s.id, s.last_seen, s.created_at, s.user_agent, u.id AS user_id, u.username, u.name, u.role "
                "FROM sessions s "
                "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.ended_at = '' AND u.active = 1",
                (_digest(token),)).fetchone()
            if row is None:
                return None
            if user_agent and row["user_agent"] and browser_family(row["user_agent"]) != browser_family(user_agent):
                return None  # a copied token: refused, without ending the real session
            seen = datetime.fromisoformat(row["last_seen"])
            too_old = now - datetime.fromisoformat(row["created_at"]) > SESSION_MAX_AGE
            if too_old or now - seen > timedelta(minutes=max(5, int(idle_minutes))):
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


    # ------------------------------------------------------- password reset by email
    def start_password_reset(self, username: str) -> tuple[str, str] | None:
        """A one-time code for an administrator who forgot the password, to be sent to the business email.
        Returns (code, email), or None when it does not apply (unknown user, not an administrator, no business
        email, or too many requests): the caller must answer the same either way."""
        from .mailer import valid_email

        now = clock.now()
        with self.db.tx() as cur:
            email = (self._settings(cur).get("email") or "").strip()
            user = cur.execute("SELECT id FROM users WHERE username = ? AND active = 1 AND role = 'admin'",
                               (str(username or "").strip().lower(),)).fetchone()
            if user is None or not valid_email(email):
                return None
            recent = cur.execute("SELECT COUNT(*) AS n FROM password_resets WHERE user_id = ? AND created_at >= ?",
                                 (user["id"], (now - timedelta(hours=1)).isoformat(timespec="seconds"))).fetchone()
            today = cur.execute("SELECT COUNT(*) AS n FROM password_resets WHERE user_id = ? AND created_at >= ?",
                                (user["id"], (now - timedelta(days=1)).isoformat(timespec="seconds"))).fetchone()
            if recent["n"] >= RESET_MAX_PER_HOUR or today["n"] >= RESET_MAX_PER_DAY:
                return None
            code = f"{secrets.randbelow(10 ** RESET_DIGITS):0{RESET_DIGITS}d}"
            cur.execute("UPDATE password_resets SET used_at = ? WHERE user_id = ? AND used_at = ''",
                        (now.isoformat(timespec="seconds"), user["id"]))  # only the newest code works
            cur.execute("INSERT INTO password_resets(user_id, code_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
                        (user["id"], hash_secret(code), now.isoformat(timespec="seconds"),
                         (now + RESET_VALID).isoformat(timespec="seconds")))
            self._audit(cur, username, "recuperacion_por_email", "código enviado al email del negocio")
        return code, email

    def finish_password_reset(self, username: str, code: str, new_secret: str) -> bool:
        """Set a new password with the emailed code. Every device of that person is signed out."""
        now = clock.now()
        check_secret_strength(new_secret, "admin")
        with self.db.tx() as cur:
            row = cur.execute(
                "SELECT r.id, r.user_id, r.code_hash, r.attempts FROM password_resets r JOIN users u ON u.id = r.user_id "
                "WHERE u.username = ? AND u.active = 1 AND u.role = 'admin' AND r.used_at = '' AND r.expires_at > ? "
                "ORDER BY r.id DESC LIMIT 1",
                (str(username or "").strip().lower(), now.isoformat(timespec="seconds"))).fetchone()
            if row is None or row["attempts"] >= RESET_MAX_ATTEMPTS:
                return False
            if not verify_secret(str(code or "").strip(), row["code_hash"]):
                cur.execute("UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
                return False
            cur.execute("UPDATE password_resets SET used_at = ? WHERE id = ?", (now.isoformat(timespec="seconds"), row["id"]))
            cur.execute("UPDATE users SET secret_hash = ?, failed_attempts = 0, lockouts = 0, locked_until = '', "
                        "must_change = 0 WHERE id = ?", (hash_secret(new_secret), row["user_id"]))
            self._end_user_sessions(cur, row["user_id"])
            self._audit(cur, username, "contraseña_cambiada", "con código enviado por email")
        return True
