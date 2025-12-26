from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.crypto import encrypt_secret
from app.db import session_scope
from app.models import ProviderKey
from app.schemas import Provider, ProviderKeyUpsertRequest

router = APIRouter()


@router.put("/settings/keys/{provider}")
def upsert_provider_key(provider: Provider, body: ProviderKeyUpsertRequest):
    ct = encrypt_secret(body.api_key)

    with session_scope() as session:
        existing = (
            session.query(ProviderKey)
            .filter(ProviderKey.provider == provider)
            .filter(ProviderKey.scope == "user")
            .filter(ProviderKey.scope_id == "local")
            .one_or_none()
        )
        if existing is None:
            pk = ProviderKey(provider=provider, key_ciphertext=ct, enabled=body.enabled)
            session.add(pk)
        else:
            existing.key_ciphertext = ct
            existing.enabled = body.enabled

        session.commit()

    return {"ok": True}
