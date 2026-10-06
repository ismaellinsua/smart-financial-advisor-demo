"""Small secrets kept encrypted in the database (the two-step verification keys), with the server's DATA_KEY.

A copy of the database alone then does not give anyone the codes of an account. Without DATA_KEY the keys are kept as
before (and work as before); once it is set, new ones are encrypted and old ones are encrypted at the next sign-in.
If DATA_KEY is lost, two-step verification stops working for those accounts: administrators get back in with a
recovery code and set it up again.

DATA_KEY becomes the encryption key through scrypt, a deliberately slow and memory-hungry function: someone holding a
copy of the database cannot try millions of guesses for it per second. Use a long random value all the same (at least
32 characters; a shorter one is used but reported in the server log).
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from . import config, logs

PREFIX = "enc2:"  # scrypt-derived key
LEGACY_PREFIX = "enc1:"  # SHA-256-derived key (first version); still read, re-encrypted at the next use
MIN_KEY_LENGTH = 32
log = logs.get("secretbox")


@lru_cache(maxsize=4)
def _fernet(text: str, version: int) -> Fernet:
    if version == 1:
        raw = hashlib.sha256(f"nirkana-data-key:{text}".encode()).digest()
    else:
        if len(text) < MIN_KEY_LENGTH:
            log.warning("data_key_short length=%s minimum=%s", len(text), MIN_KEY_LENGTH)
        raw = hashlib.scrypt(text.encode(), salt=b"nirkana-data-key-v2", n=2 ** 15, r=8, p=1, maxmem=64 * 2 ** 20,
                             dklen=32)
    return Fernet(base64.urlsafe_b64encode(raw))


def _key() -> str:
    return config.value("data_key")


def is_sealed(value: str) -> bool:
    return str(value or "").startswith((PREFIX, LEGACY_PREFIX))


def needs_sealing(value: str) -> bool:
    """Stored in the clear or with the older key derivation, while DATA_KEY is set: worth encrypting again."""
    return bool(value) and bool(_key()) and not str(value).startswith(PREFIX)


def seal(value: str) -> str:
    """Encrypted when DATA_KEY is set; unchanged otherwise (and unchanged if it is empty or already sealed)."""
    key = _key()
    if not value or str(value).startswith(PREFIX) or not key:
        return value
    plain = unseal(value) if str(value).startswith(LEGACY_PREFIX) else value
    if not plain:
        return value  # an older value we cannot read: leave it as it is
    return PREFIX + _fernet(key, 2).encrypt(plain.encode()).decode()


def unseal(value: str) -> str:
    """The plain secret; "" when it cannot be read (no DATA_KEY or a different one), which fails the check safely."""
    if not is_sealed(value):
        return value or ""
    key = _key()
    if not key:
        log.error("secret_unreadable reason=no_data_key")
        return ""
    version, body = (2, value[len(PREFIX):]) if value.startswith(PREFIX) else (1, value[len(LEGACY_PREFIX):])
    try:
        return _fernet(key, version).decrypt(body.encode()).decode()
    except InvalidToken:
        log.error("secret_unreadable reason=data_key_changed")
        return ""
