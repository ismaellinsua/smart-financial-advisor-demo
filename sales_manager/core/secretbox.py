"""Small secrets kept encrypted in the database (the two-step verification keys), with the server's DATA_KEY.

A copy of the database alone then does not give anyone the codes of an account. Without DATA_KEY the keys are kept as
before (and work as before); once it is set, new ones are encrypted and old ones are encrypted at the next sign-in.
If DATA_KEY is lost, two-step verification stops working for those accounts: administrators get back in with a
recovery code and set it up again.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from . import config, logs

PREFIX = "enc1:"
log = logs.get("secretbox")


def _box() -> Fernet | None:
    text = config.value("data_key")
    if not text:
        return None
    # Any long random text works as DATA_KEY; Fernet wants 32 bytes, so derive them.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(f"nirkana-data-key:{text}".encode()).digest()))


def is_sealed(value: str) -> bool:
    return str(value or "").startswith(PREFIX)


def seal(value: str) -> str:
    """Encrypted when DATA_KEY is set; unchanged otherwise (and unchanged if it is empty or already sealed)."""
    box = _box()
    if not value or is_sealed(value) or box is None:
        return value
    return PREFIX + box.encrypt(value.encode()).decode()


def unseal(value: str) -> str:
    """The plain secret; "" when it cannot be read (no DATA_KEY or a different one), which fails the check safely."""
    if not is_sealed(value):
        return value or ""
    box = _box()
    try:
        return box.decrypt(value[len(PREFIX):].encode()).decode() if box else ""
    except InvalidToken:
        log.error("secret_unreadable reason=data_key_changed")
        return ""
    finally:
        if box is None:
            log.error("secret_unreadable reason=no_data_key")
