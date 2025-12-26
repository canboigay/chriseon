from __future__ import annotations

import base64

from cryptography.fernet import Fernet

from worker.settings import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    raw = base64.b64decode(settings.key_encryption_master_key_b64)
    if len(raw) != 32:
        raise ValueError("KEY_ENCRYPTION_MASTER_KEY_B64 must decode to exactly 32 bytes")
    return Fernet(base64.urlsafe_b64encode(raw))


def decrypt_secret(ciphertext: str) -> str:
    pt = _fernet().decrypt(ciphertext.encode("utf-8"))
    return pt.decode("utf-8")
