"""Security helpers: secret hashing, input limits and safe exports."""

import base64
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import quote

import pandas as pd

# PBKDF2-HMAC-SHA256 as recommended by OWASP. The iteration count is stored in each hash,
# so it can be raised later without breaking existing accounts.
PBKDF2_ITERATIONS = 600_000

ROLES = {
    "admin": "Administrador",
    "encargado": "Encargado",
    "empleado": "Empleado",
}
ROLE_RANK = {"empleado": 0, "encargado": 1, "admin": 2}

# Server-side limits on free text, so a single field cannot bloat the database or the documents.
MAX_LENGTHS = {"name": 120, "short": 60, "email": 254, "address": 250, "notes": 500}

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,30}$")


def hash_secret(secret: str, iterations: int | None = None) -> str:
    iterations = iterations or PBKDF2_ITERATIONS
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_secret(secret: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(salt), int(iterations)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, digest)


# A hash of a random secret, checked when the username does not exist, so a failed login takes the
# same time whether or not the user exists (no username probing by timing).
DUMMY_HASH = hash_secret(secrets.token_hex(16))


# The most used passwords and PINs (public leaked-password lists), plus obvious ones for this app. Compared lower-cased.
COMMON_SECRETS = {
    "password", "password1", "password123", "passw0rd", "contraseña", "contraseña1", "contrasena", "contrasena1",
    "12345678", "123456789", "1234567890", "87654321", "11223344", "12341234", "123123123",
    "121212", "123123", "112233", "131313", "159753", "147258", "147258369", "159357", "696969", "102030",
    "qwerty", "qwerty123", "qwertyuiop", "1q2w3e4r", "1qaz2wsx", "123qwe", "abc123", "abcd1234", "a1b2c3d4",
    "admin", "admin123", "admin1234", "administrador", "administrador1", "iloveyou", "teamo123", "letmein1",
    "nirkana", "nirkana1", "nirkana123", "nirkana2026", "bienvenido1", "hola1234",
}
MIN_PIN_LENGTH = 6


def _is_trivial_pin(secret: str) -> bool:
    """Same digit repeated or a straight run (123456, 654321): the first ones anyone tries."""
    if not secret.isdigit():
        return False
    steps = {int(b) - int(a) for a, b in zip(secret, secret[1:])}
    return len(steps) == 1 and steps <= {-1, 0, 1}


def check_secret_strength(secret: str, role: str) -> None:
    """Administrators need a real password; everyone else a PIN or password of at least 6 characters."""
    if len(secret) > 128:
        raise ValueError("La contraseña es demasiado larga (máximo 128 caracteres).")
    if role == "admin":
        if len(secret) < 8:
            raise ValueError("La contraseña del administrador debe tener al menos 8 caracteres.")
        if not (any(ch.isalpha() for ch in secret) and any(not ch.isalpha() for ch in secret)):
            raise ValueError("Usa una contraseña con letras y números (o símbolos), no solo dígitos o solo letras.")
    elif len(secret) < MIN_PIN_LENGTH:
        raise ValueError(f"El PIN o contraseña debe tener al menos {MIN_PIN_LENGTH} caracteres.")
    if secret.lower() in COMMON_SECRETS or _is_trivial_pin(secret):
        raise ValueError("Ese PIN o contraseña es demasiado fácil de adivinar.")


# ------------------------------------------------------------- recovery codes
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I
RECOVERY_CODE_COUNT = 8
RECOVERY_ITERATIONS = 20_000  # ~60 random bits per code: a fast hash is enough


def new_recovery_code() -> str:
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def normalize_recovery_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())


# ----------------------------------------------- two-step verification (TOTP)
def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    """RFC 6238 code, the one shown by Google Authenticator, Microsoft Authenticator and similar apps."""
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = int((time.time() if at is None else at) // step)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 10 ** digits
    return f"{value:0{digits}d}"


def totp_step(secret: str, code: str, at: float | None = None, step: int = 30) -> int | None:
    """The time step a valid code belongs to (current, previous or next: phone clocks drift), or None. Callers that
    remember the last step used can refuse the same code twice."""
    code = re.sub(r"\D", "", str(code or ""))
    if not secret or len(code) != 6:
        return None
    now = time.time() if at is None else at
    for drift in (-step, 0, step):
        if hmac.compare_digest(totp_code(secret, now + drift), code):
            return int((now + drift) // step)
    return None


def verify_totp(secret: str, code: str, at: float | None = None) -> bool:
    return totp_step(secret, code, at) is not None


def totp_uri(secret: str, account: str, issuer: str = "NirKanA") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}"


def clean_text(value, field: str, kind: str = "name", required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"El campo «{field}» es obligatorio.")
    limit = MAX_LENGTHS[kind]
    if len(text) > limit:
        raise ValueError(f"El campo «{field}» es demasiado largo (máximo {limit} caracteres).")
    return text


def is_safe_identifier(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", name))


def csv_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Neutralise spreadsheet formulas (CSV injection): text starting with = + - @ is prefixed with '."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].map(
                lambda v: "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v
            )
    return out
