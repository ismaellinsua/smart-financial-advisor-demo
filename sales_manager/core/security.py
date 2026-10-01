"""Security helpers: secret hashing, input limits and safe exports."""

import hashlib
import hmac
import re
import secrets

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


def check_secret_strength(secret: str, role: str) -> None:
    """Administrators need a real password; staff may use a PIN of at least 4 digits."""
    if role == "admin":
        if len(secret) < 8:
            raise ValueError("La contraseña del administrador debe tener al menos 8 caracteres.")
        if not (any(ch.isalpha() for ch in secret) and any(not ch.isalpha() for ch in secret)):
            raise ValueError("Usa una contraseña con letras y números (o símbolos), no solo dígitos o solo letras.")
    elif len(secret) < 4:
        raise ValueError("El PIN o contraseña debe tener al menos 4 caracteres.")
    if len(secret) > 128:
        raise ValueError("La contraseña es demasiado larga (máximo 128 caracteres).")
    if secret in {"1234", "0000", "1111", "12345", "123456", "password", "contraseña", "12345678"}:
        raise ValueError("Esa contraseña es demasiado fácil de adivinar.")


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
