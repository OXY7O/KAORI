from __future__ import annotations

from app.extensions.db import db
from app.models import IdentityProvider


def get_identity_provider(provider_id: int) -> IdentityProvider | None:
    return db.session.get(IdentityProvider, provider_id)
