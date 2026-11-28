"""Exact provider-instance proof fence for external authentication (#5365)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select

from app.access.authentication.results import ExternalCredentialProof
from app.access.authentication.session import AuthSessionError
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider


def parse_external_credential_proof(pending: Mapping[str, object]) -> ExternalCredentialProof | None:
    provider_id = pending.get('provider_id')
    revision = pending.get('provider_revision')
    link_id = pending.get('provider_link_id')
    if (
        not isinstance(provider_id, int) or isinstance(provider_id, bool) or provider_id < 1
        or not isinstance(revision, int) or isinstance(revision, bool) or revision < 1
        or not isinstance(link_id, int) or isinstance(link_id, bool) or link_id < 1
    ):
        return None
    return ExternalCredentialProof(provider_id, revision, link_id)


def lock_provider_revision(provider_id: int, revision: int, *, source: str) -> IdentityProvider:
    """Serialize proof admission with provider administration; caller owns transaction."""
    provider = db.session.execute(
        select(IdentityProvider)
        .where(
            IdentityProvider.id == provider_id,
            IdentityProvider.authentication_revision == revision,
            IdentityProvider.provider_key == source,
            IdentityProvider.enabled.is_(True),
        )
        .with_for_update(of=IdentityProvider)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if provider is None:
        raise AuthSessionError('External provider authentication proof is stale.')
    return provider


def lock_external_credential_proof(
    user_id: int, source: str, proof: ExternalCredentialProof | None
) -> None:
    if proof is None:
        raise AuthSessionError('Verified external credential proof is missing.')
    lock_provider_revision(proof.provider_id, proof.revision, source=source)
    link_id = db.session.execute(
        select(ExternalIdentityLink.id).where(
            ExternalIdentityLink.id == proof.link_id,
            ExternalIdentityLink.provider_id == proof.provider_id,
            ExternalIdentityLink.user_id == user_id,
        )
    ).scalar_one_or_none()
    if link_id is None:
        raise AuthSessionError('External identity binding changed.')
