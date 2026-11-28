"""Strict LDAP assurance for the already admitted linked identity (#5374)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.identity_provider.adapters.ldap.client import ExternalProviderError, LdapDirectoryClient
from app.access.authentication.identity_provider.proof import lock_provider_revision, parse_external_credential_proof
from app.access.authentication.password_policy import LOCAL_PASSWORD_MAX_LENGTH
from app.access.authentication.results import ExternalCredentialProof
from app.extensions.db import db
from app.models import ExternalIdentityLink, IdentityProvider


class LdapReauthenticationError(ValueError):
    """Generic provider reauthentication rejection, never remote diagnostic text."""


def _binding_fingerprint(link: ExternalIdentityLink) -> str:
    return sha256(f'{link.subject}\x00{link.distinguished_name or ""}'.encode()).hexdigest()


@dataclass(frozen=True)
class LdapReauthenticationProof:
    credential: ExternalCredentialProof
    subject: str
    binding_fingerprint: str
    verified_at: datetime

    def to_record(self) -> dict[str, int | str]:
        return {
            'provider_id': self.credential.provider_id,
            'provider_revision': self.credential.revision,
            'provider_link_id': self.credential.link_id,
            'subject': self.subject,
            'binding_fingerprint': self.binding_fingerprint,
            'verified_at': self.verified_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: object) -> LdapReauthenticationProof | None:
        if not isinstance(record, dict):
            return None
        credential = parse_external_credential_proof(record)
        subject = record.get('subject')
        fingerprint = record.get('binding_fingerprint')
        verified = record.get('verified_at')
        if (
            credential is None
            or not isinstance(subject, str)
            or not subject
            or not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or not isinstance(verified, str)
        ):
            return None
        try:
            verified_at = datetime.fromisoformat(verified)
        except ValueError:
            return None
        if verified_at.tzinfo is None:
            return None
        return cls(credential, subject, fingerprint, verified_at.astimezone(UTC))


def _linked_directory(user_id: int) -> tuple[ExternalIdentityLink, IdentityProvider]:
    # Count all directory bindings, including disabled instances; no ambiguous fallback.
    rows = db.session.execute(
        select(ExternalIdentityLink, IdentityProvider)
        .join(IdentityProvider, IdentityProvider.id == ExternalIdentityLink.provider_id)
        .where(ExternalIdentityLink.user_id == user_id, IdentityProvider.provider_key == 'ldap')
        .limit(2)
    ).all()
    if len(rows) != 1:
        raise LdapReauthenticationError('Directory identity binding is unavailable.')
    link, provider = rows[0]
    if not provider.enabled or provider.adapter_key != 'ldap' or not link.distinguished_name or not link.subject:
        raise LdapReauthenticationError('Directory identity binding is unavailable.')
    return link, provider


def ldap_reauthentication_available(user_id: int) -> bool:
    """Read configuration only; never perform a remote authentication on GET."""
    try:
        _, provider = _linked_directory(user_id)
        LdapDirectoryClient(provider, allow_plaintext=False)
    except (LdapReauthenticationError, ExternalProviderError):
        return False
    except SQLAlchemyError:
        db.session.rollback()
        return False
    return True


def reauthenticate_ldap_account(user_id: int, password: str | None) -> LdapReauthenticationProof:
    if not password or len(password) > LOCAL_PASSWORD_MAX_LENGTH:
        raise LdapReauthenticationError('Directory credential was not accepted.')
    try:
        link, provider = _linked_directory(user_id)
        credential = ExternalCredentialProof(provider.id, provider.authentication_revision, link.id)
        subject = link.subject
        dn = link.distinguished_name
        fingerprint = _binding_fingerprint(link)
        client = LdapDirectoryClient(provider, allow_plaintext=False)
        # Snapshot only non-secret identifiers and client configuration, then release
        # the read transaction before performing network I/O. Caller owns a fresh transaction.
        db.session.rollback()
        verified_at = datetime.now(UTC)
        if dn is None or not client.reauthenticate_linked_identity(dn, password, subject):
            raise LdapReauthenticationError('Directory credential or identity was not accepted.')
        return LdapReauthenticationProof(credential, subject, fingerprint, verified_at)
    except ExternalProviderError as exc:
        raise LdapReauthenticationError('Directory reauthentication is unavailable.') from exc


def lock_ldap_reauthentication_proof(user_id: int, proof: LdapReauthenticationProof) -> None:
    """Lock the same provider/link before account/factor mutation."""
    credential = proof.credential
    provider = lock_provider_revision(credential.provider_id, credential.revision, source='ldap')
    if provider.adapter_key != 'ldap':
        raise LdapReauthenticationError('Directory provider binding changed.')
    link = db.session.execute(
        select(ExternalIdentityLink)
        .where(
            ExternalIdentityLink.id == credential.link_id,
            ExternalIdentityLink.provider_id == credential.provider_id,
            ExternalIdentityLink.user_id == user_id,
        )
        .with_for_update(of=ExternalIdentityLink)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if link is None or link.subject != proof.subject or _binding_fingerprint(link) != proof.binding_fingerprint:
        raise LdapReauthenticationError('Directory identity binding changed.')
    # Recheck uniqueness after remote verification; never admit an ambiguous binding.
    current, _ = _linked_directory(user_id)
    if current.id != credential.link_id:
        raise LdapReauthenticationError('Directory identity binding changed.')
