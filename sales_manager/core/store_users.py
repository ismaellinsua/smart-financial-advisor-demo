"""Staff accounts: creation, roles, sign-in with lockout, recovery codes and two-step verification. Mixed into
`Store`."""

from datetime import datetime, timedelta

import pandas as pd

from . import clock
from .errors import AuthError, PermissionDenied
from .secretbox import needs_sealing, seal, unseal
from .security import (
    DUMMY_HASH, RECOVERY_CODE_COUNT, RECOVERY_ITERATIONS, ROLE_RANK, ROLES, USERNAME_RE, check_secret_strength,
    clean_text, hash_secret, new_recovery_code, normalize_recovery_code, totp_step, verify_secret, verify_totp,
)

# An account locks for a fixed, short time after many failures. A long or growing lock would let anyone who knows a
# username keep the business out of its own till; guessing is slowed per device instead (ui/auth.py), PINs are
# long enough to make it impractical, and administrators can always get back in with a recovery code.
MAX_FAILED_LOGINS = 10
LOCKOUT_MINUTES = 15


class UsersMixin:
    # --------------------------------------------------------------------- users
    # Users and the audit log are never part of backups or templates: credentials stay on the server.
    _USER_FIELDS = ("id, username, name, role, active, last_login, created_at, location_id, "
                    "CASE WHEN totp_secret <> '' THEN 1 ELSE 0 END AS two_factor")

    def has_users(self) -> bool:
        # Never cached: it decides whether the first-administrator screen is shown.
        with self.db.tx() as cur:
            return cur.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def users(self) -> pd.DataFrame:
        return self._frame(f"SELECT {self._USER_FIELDS} FROM users ORDER BY active DESC, name")

    def set_user_location(self, user_id: int, location_id: int | None) -> None:
        """Pin a person to one location (their till, cash and tables), or None to let them work in any."""
        with self.db.tx() as cur:
            if location_id is not None and not cur.execute("SELECT 1 FROM locations WHERE id = ?",
                                                            (int(location_id),)).fetchone():
                raise ValueError("Ese local no existe.")
            cur.execute("UPDATE users SET location_id = ? WHERE id = ?",
                        (None if location_id is None else int(location_id), int(user_id)))

    def user(self, user_id: int) -> dict | None:
        with self.db.tx() as cur:
            return cur.execute(f"SELECT {self._USER_FIELDS} FROM users WHERE id = ?", (int(user_id),)).fetchone()

    def create_user(self, name: str, username: str, role: str, secret: str, by: str = "") -> int:
        name = clean_text(name, "Nombre", required=True)
        username = str(username or "").strip().lower()
        if not USERNAME_RE.fullmatch(username):
            raise ValueError("El usuario debe tener de 3 a 30 caracteres: letras minúsculas, números, punto, guion "
                             "o guion bajo.")
        if role not in ROLES:
            raise ValueError("Rol no válido.")
        check_secret_strength(secret, role)
        try:
            with self.db.tx() as cur:
                row = cur.execute(
                    "INSERT INTO users(username, name, role, secret_hash, created_at) VALUES (?, ?, ?, ?, ?) "
                    "RETURNING id",
                    (username, name, role, hash_secret(secret), clock.now().isoformat(timespec="seconds")),
                ).fetchone()
                self._audit(cur, by or username, "usuario_creado", f"{username} ({ROLES[role]})")
                return row["id"]
        except self.db.integrity_errors as exc:
            raise ValueError(f"Ya existe un usuario «{username}».") from exc

    def _active_admins(self, cur) -> int:
        return cur.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND active = 1").fetchone()["n"]

    def update_user(self, user_id: int, *, name: str | None = None, role: str | None = None,
                    active: bool | None = None, by: str = "", as_role: str | None = None) -> None:
        self._require(as_role, "admin")
        user_id = int(user_id)
        with self.db.tx() as cur:
            user = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:
                raise ValueError("Usuario no encontrado.")
            new_role = role if role is not None else user["role"]
            new_active = int(active) if active is not None else user["active"]
            if new_role not in ROLES:
                raise ValueError("Rol no válido.")
            losing_admin = user["role"] == "admin" and user["active"] and (new_role != "admin" or not new_active)
            if losing_admin and self._active_admins(cur) <= 1:
                raise ValueError("Debe quedar al menos un administrador activo.")
            new_name = clean_text(name, "Nombre", required=True) if name is not None else user["name"]
            cur.execute("UPDATE users SET name = ?, role = ?, active = ? WHERE id = ?",
                        (new_name, new_role, new_active, user_id))
            if not new_active:
                self._end_user_sessions(cur, user_id)
            self._audit(cur, by, "usuario_modificado",
                        f"{user['username']}: rol {ROLES[new_role]}, {'activo' if new_active else 'desactivado'}")

    def set_user_secret(self, user_id: int, secret: str, by: str = "", as_role: str | None = None) -> None:
        self._require(as_role, "admin")
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, role FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if user is None:
                raise ValueError("Usuario no encontrado.")
            check_secret_strength(secret, user["role"])
            # Chosen by someone else (an administrator): the person must pick their own at the next sign-in, so only
            # they know it and what they sign stays theirs.
            must_change = int(bool(by) and by != user["username"])
            cur.execute("UPDATE users SET secret_hash = ?, failed_attempts = 0, lockouts = 0, locked_until = '', "
                        "must_change = ? WHERE id = ?",
                        (hash_secret(secret), must_change, int(user_id)))
            self._end_user_sessions(cur, user_id)
            self._audit(cur, by, "contraseña_cambiada", user["username"])

    def authorize(self, username: str, secret: str, needed: str = "encargado", otp: str = "",
                  purpose: str = "", now: float | None = None) -> dict:
        """A manager confirms an action at someone else's till. Same password checks and log as a login, but its
        failures have their own counter (core/throttle.py, per manager): someone at the till can neither lock the
        manager out of their own sign-in nor keep guessing their PIN."""
        key = "autorizacion:" + str(username or "").strip().lower()
        if minutes := self.throttle_blocked_minutes(key, now):
            raise AuthError(f"Demasiados intentos para autorizar con esa cuenta. Espera {minutes} min.")
        try:
            user = self.authenticate(username, secret, otp=otp, purpose=purpose or "autorización")
        except AuthError:
            # Fixed 15-minute blocks: whoever keeps failing at the till cannot leave the manager unable to approve
            # anything for a whole day.
            self.throttle_failed(key, now, grow=False)
            raise
        self.throttle_succeeded(key)
        if not self.can(user["role"], needed):
            raise AuthError("Esa persona no puede autorizarlo: hace falta un encargado o el administrador.")
        return user

    def authenticate(self, username: str, secret: str, now: datetime | None = None, otp: str = "",
                     purpose: str = "") -> dict:
        """Check a login (and the two-step code when the account has it). Locks the account briefly after many
        failures. The error never says which part was wrong, nor whether the user exists."""
        now = now or clock.now()
        username = str(username or "").strip().lower()
        # One answer for every failure, a locked account included: it must not reveal which usernames exist.
        generic = AuthError("Usuario, contraseña o código incorrectos. Tras varios fallos seguidos, la cuenta espera "
                            f"{LOCKOUT_MINUTES} minutos (el administrador puede entrar con un código de recuperación).")
        locked = ""
        with self.db.tx() as cur:
            user = cur.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user is None or not user["active"]:
                verify_secret(secret, DUMMY_HASH)  # same work as a real check: no hints from timing
                self._audit(cur, username, "acceso_fallido", "usuario inexistente o desactivado")
                user = None
            if user is None:
                pass  # the failed attempt is recorded; raise once the transaction has committed
            elif user["locked_until"] and datetime.fromisoformat(user["locked_until"]) > now:
                verify_secret(secret, DUMMY_HASH)  # same time as any other answer
                self._audit(cur, username, "acceso_bloqueado", "cuenta en espera por intentos fallidos")
            elif verify_secret(secret, user["secret_hash"]) and self._totp_ok(cur, user, otp):
                if purpose:  # an authorisation, not a sign-in
                    cur.execute("UPDATE users SET failed_attempts = 0, locked_until = '' WHERE id = ?", (user["id"],))
                    self._audit(cur, username, "autorizacion", purpose)
                else:
                    cur.execute("UPDATE users SET failed_attempts = 0, lockouts = 0, locked_until = '', last_login = ? "
                                "WHERE id = ?", (now.isoformat(timespec="seconds"), user["id"]))
                    self._audit(cur, username, "acceso", "")
                return {**{k: user[k] for k in ("id", "username", "name", "role")},
                        "must_change": bool(user["must_change"])}
            elif purpose:  # a failed authorisation: counted apart (see authorize), never locks the account
                self._audit(cur, username, "autorizacion_fallida", purpose)
            else:
                failed = user["failed_attempts"] + 1
                if failed >= MAX_FAILED_LOGINS:
                    locked = (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
                    failed = 0
                cur.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                            (failed, locked, user["id"]))
                self._audit(cur, username, "acceso_fallido", "cuenta bloqueada" if locked else f"intento {failed}")
        raise generic

    @staticmethod
    def _totp_ok(cur, user, otp: str) -> bool:
        """No two-step verification, or a code from its app not used before (a code seen over someone's shoulder or
        captured on the way cannot be replayed). Encrypts an old plain key the first time DATA_KEY allows it."""
        if not user["totp_secret"]:
            return True
        step = totp_step(unseal(user["totp_secret"]), otp)
        if step is None or step <= int(user["totp_last_step"] or 0):
            return False
        sealed = seal(user["totp_secret"]) if needs_sealing(user["totp_secret"]) else user["totp_secret"]
        cur.execute("UPDATE users SET totp_last_step = ?, totp_secret = ? WHERE id = ?", (step, sealed, user["id"]))
        return True

    def confirm_secret(self, user_id: int, secret: str) -> bool:
        """Re-check the signed-in person's PIN or password before an action that replaces data."""
        with self.db.tx() as cur:
            user = cur.execute("SELECT secret_hash FROM users WHERE id = ? AND active = 1", (int(user_id),)).fetchone()
        return bool(user and secret and verify_secret(secret, user["secret_hash"]))

    def change_own_secret(self, user_id: int, current: str, new: str) -> None:
        """A person changes their own PIN or password, proving they know the current one."""
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, role, secret_hash FROM users WHERE id = ? AND active = 1",
                               (int(user_id),)).fetchone()
            if user is None or not verify_secret(current, user["secret_hash"]):
                raise ValueError("El PIN o contraseña actual no es correcto.")
            if verify_secret(new, user["secret_hash"]):
                raise ValueError("El nuevo PIN o contraseña debe ser distinto del actual.")
            check_secret_strength(new, user["role"])
            cur.execute("UPDATE users SET secret_hash = ?, must_change = 0 WHERE id = ?", (hash_secret(new), int(user_id)))
            self._end_user_sessions(cur, user_id)  # other devices must sign in again with the new one
            self._audit(cur, user["username"], "contraseña_cambiada", "por la propia persona")

    # ------------------------------------------------- administrator recovery codes
    def create_recovery_codes(self, user_id: int, by: str = "") -> list[str]:
        """New single-use codes for an administrator; the previous unused ones stop working. Shown only once."""
        codes = [new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        stamp = clock.now().isoformat(timespec="seconds")
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, role FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if user is None or user["role"] != "admin":
                raise ValueError("Solo los administradores tienen códigos de recuperación.")
            cur.execute("DELETE FROM recovery_codes WHERE user_id = ? AND used_at = ''", (int(user_id),))
            cur.executemany("INSERT INTO recovery_codes(user_id, code_hash, created_at) VALUES (?, ?, ?)",
                            [(int(user_id), hash_secret(normalize_recovery_code(c), RECOVERY_ITERATIONS), stamp)
                             for c in codes])
            self._audit(cur, by or user["username"], "codigos_recuperacion_generados", user["username"])
        return codes

    def recovery_codes_left(self, user_id: int) -> int:
        with self.db.tx() as cur:
            return int(cur.execute("SELECT COUNT(*) AS n FROM recovery_codes WHERE user_id = ? AND used_at = ''",
                                   (int(user_id),)).fetchone()["n"])

    def recover_with_code(self, username: str, code: str, new_secret: str) -> dict:
        """An administrator who forgot the password, lost the phone or is locked out sets a new password with one
        of their recovery codes. It also unlocks the account and turns two-step verification off (set it up again).
        """
        username = str(username or "").strip().lower()
        code = normalize_recovery_code(code)
        generic = AuthError("Usuario o código de recuperación incorrectos.")
        with self.db.tx() as cur:
            user = cur.execute("SELECT * FROM users WHERE username = ? AND active = 1 AND role = 'admin'",
                               (username,)).fetchone()
            rows = [] if user is None else cur.execute(
                "SELECT id, code_hash FROM recovery_codes WHERE user_id = ? AND used_at = ''", (user["id"],)).fetchall()
            match = next((r for r in rows if verify_secret(code, r["code_hash"])), None)
            if match is None:
                self._audit(cur, username, "recuperacion_fallida", "")
            else:
                check_secret_strength(new_secret, "admin")
                cur.execute("UPDATE recovery_codes SET used_at = ? WHERE id = ?",
                            (clock.now().isoformat(timespec="seconds"), match["id"]))
                cur.execute("UPDATE users SET secret_hash = ?, totp_secret = '', failed_attempts = 0, lockouts = 0, "
                            "locked_until = '', must_change = 0 WHERE id = ?", (hash_secret(new_secret), user["id"]))
                self._end_user_sessions(cur, user["id"])
                self._audit(cur, username, "acceso_recuperado", "con código de recuperación")
                return {k: user[k] for k in ("id", "username", "name", "role")}
        raise generic

    # ------------------------------------------------- two-step verification (TOTP)
    def enable_two_factor(self, user_id: int, secret: str, code: str) -> None:
        if not verify_totp(secret, code):
            raise ValueError("El código no es correcto. Comprueba que la hora del móvil es la correcta y prueba otra vez.")
        with self.db.tx() as cur:
            user = cur.execute("SELECT username FROM users WHERE id = ?", (int(user_id),)).fetchone()
            cur.execute("UPDATE users SET totp_secret = ?, totp_last_step = 0 WHERE id = ?", (seal(secret), int(user_id)))
            self._audit(cur, user["username"], "verificacion_dos_pasos", "activada")

    def reset_two_factor(self, user_id: int, by: str = "", as_role: str | None = None) -> None:
        """An administrator turns off someone's two-step verification (e.g. a lost phone); they set it up again."""
        self._require(as_role, "admin")
        with self.db.tx() as cur:
            user = cur.execute("SELECT username FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if user is None:
                raise ValueError("Usuario no encontrado.")
            cur.execute("UPDATE users SET totp_secret = '', totp_last_step = 0 WHERE id = ?", (int(user_id),))
            self._end_user_sessions(cur, user_id)
            self._audit(cur, by, "verificacion_dos_pasos", f"{user['username']}: quitada por un administrador")

    def disable_two_factor(self, user_id: int, code: str) -> None:
        with self.db.tx() as cur:
            user = cur.execute("SELECT username, totp_secret FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if not user or not verify_totp(unseal(user["totp_secret"]), code):
                raise ValueError("El código no es correcto.")
            cur.execute("UPDATE users SET totp_secret = '' WHERE id = ?", (int(user_id),))
            self._audit(cur, user["username"], "verificacion_dos_pasos", "desactivada")

    @staticmethod
    def _audit(cur, username: str, action: str, detail: str = "") -> None:
        cur.execute("INSERT INTO audit_log(happened_at, username, action, detail) VALUES (?, ?, ?, ?)",
                    (clock.now().isoformat(timespec="seconds"), str(username)[:60], action, str(detail)[:500]))

    def audit(self, username: str, action: str, detail: str = "") -> None:
        with self.db.tx() as cur:
            self._audit(cur, username, action, detail)

    def audit_log(self, limit: int = 300) -> pd.DataFrame:
        df = self._frame("SELECT happened_at, username, action, detail FROM audit_log ORDER BY id DESC LIMIT ?",
                         (int(limit),))
        df["happened_at"] = pd.to_datetime(df["happened_at"])
        return df

    @staticmethod
    def can(role: str, needed: str) -> bool:
        return ROLE_RANK.get(role, -1) >= ROLE_RANK[needed]

    @staticmethod
    def _require(as_role: str | None, needed: str) -> None:
        """Sensitive operations check the role again here, not only in the page that offers them, so a new page or
        an integration that forgot the check still cannot do them. Callers with no person behind (jobs, tests of
        the store itself) pass no role."""
        if as_role is not None and ROLE_RANK.get(as_role, -1) < ROLE_RANK[needed]:
            raise PermissionDenied("No tienes permiso para hacer esto.")
