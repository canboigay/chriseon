from __future__ import annotations

import base64

from cryptography.fernet import Fernet

from app.settings import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    raw = base64.b64decode(settings.key_encryption_master_key_b64)
    if len(raw) != 32:
        raise ValueError("KEY_ENCRYPTION_MASTER_KEY_B64 must decode to exactly 32 bytes")

    fernet_key = base64.urlsafe_b64encode(raw)
    return Fernet(fernet_key)


def encrypt_secret(plaintext: str) -> str:
    if plaintext is None:
        raise ValueError("plaintext must not be None")
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if ciphertext is None:
        raise ValueError("ciphertext must not be None")
    pt = _fernet().decrypt(ciphertext.encode("utf-8"))
    return pt.decode("utf-8")
