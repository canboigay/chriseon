from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from worker.crypto import decrypt_secret
from worker.models import ProviderKey
from worker.settings import get_settings

Provider = Literal["openai", "anthropic", "gemini", "xai"]
CredentialMode = Literal["byok", "managed", "auto"]


def _managed_key(provider: Provider) -> str | None:
    s = get_settings()
    return {
        "openai": s.openai_api_key,
        "anthropic": s.anthropic_api_key,
        "gemini": s.gemini_api_key,
        "xai": s.xai_api_key,
    }.get(provider)


def _byok_key(session: Session, provider: Provider) -> str | None:
    pk = (
        session.query(ProviderKey)
        .filter(ProviderKey.provider == provider)
        .filter(ProviderKey.scope == "user")
        .filter(ProviderKey.scope_id == "local")
        .one_or_none()
    )
    if pk is None or not pk.enabled:
        return None
    return decrypt_secret(pk.key_ciphertext)


def resolve_key(
    session: Session,
    provider: Provider,
    requested_mode: CredentialMode | None,
) -> tuple[CredentialMode, str | None]:
    mode = requested_mode or "auto"

    if mode == "managed":
        return "managed", _managed_key(provider)
    if mode == "byok":
        return "byok", _byok_key(session, provider)

    # auto
    byok = _byok_key(session, provider)
    if byok:
        return "byok", byok

    return "managed", _managed_key(provider)
