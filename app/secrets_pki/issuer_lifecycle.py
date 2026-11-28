"""Governed issuer lifecycle transactions (#5245).

Internal authenticated operator boundary only. No HTTP route, provider write,
material retrieval, signing API or worker use. PostgreSQL is mandatory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_bytes

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import load_only

from app.access.scope_policy import CredentialIssuerScope, ScopeAdmission, evaluate_exact_issuer_scope
from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import canonical_statement
from app.integrations.secrets_management.secrets_pki.providers.issuer_transit import (
    TransitIssuerObservation,
    decode_transit_signature,
    observe_transit_issuer,
)
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import (
    current_local_inventory_source,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretCredentialIssuerChallenge, SecretCredentialIssuerRevision
from app.models.vault import VaultInstance
from app.platform_operations.notifications.service import stage_operational_activity
from app.secrets_pki.credential_issuer_resolution import (
    IssuerPossessionChallenge,
    IssuerResolutionTarget,
    issuer_possession_statement,
    issuer_transition_shape_qualified,
    verify_issuer_possession,
)
from app.secrets_pki.issuer_authority import (
    DeploymentAuthority,
    resolve_custody_authority,
    resolve_deployment_authority,
)

_REQUEST = 'secrets_pki.request_credential_issuer'
_APPROVE = 'secrets_pki.approve_credential_issuer'
_REVOKE = 'secrets_pki.revoke_credential_issuer'
_DIGEST = re.compile(r'[a-f0-9]{64}')
_CHALLENGE_LIFETIME = timedelta(minutes=10)
_OBSERVATION_AGE = timedelta(seconds=60)
# Serialize all issuer writes, including empty histories, before row locks.
# Enrollment is rare; one bounded domain lock avoids cross-scope key races.
_ISSUER_LOCK = 0x4B414F5249495353


class IssuerLifecycleDenied(ValueError):
    """Non-enumerating denial; never contains provider response or secret."""


@dataclass(frozen=True, slots=True, repr=False)
class IssuerEnrollmentIntent:
    scope: CredentialIssuerScope
    expected_revision: int
    effective_until: datetime


@dataclass(frozen=True, slots=True, repr=False)
class IssuedChallenge:
    challenge_sha256: str
    statement: bytes
    expires_at: datetime
    draft_revision: int


@dataclass(frozen=True, slots=True, repr=False)
class IssuerApprovalIntent:
    scope: CredentialIssuerScope
    challenge_sha256: str
    expected_revision: int
    signature: str


def _deny() -> IssuerLifecycleDenied:
    return IssuerLifecycleDenied('Issuer lifecycle action could not be recorded.')


def _digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def begin_issuer_transaction() -> None:
    session = db.session()
    if (
        session.in_transaction()
        or session.new
        or session.dirty
        or session.deleted
        or db.engine.dialect.name != 'postgresql'
    ):
        raise _deny()
    if session.execute(text('SHOW transaction_isolation')).scalar_one() != 'read committed':
        raise _deny()
    session.execute(text("SET LOCAL lock_timeout = '5s'"))
    session.execute(text("SET LOCAL statement_timeout = '10s'"))
    session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': _ISSUER_LOCK})


def _scope_admission(actor: int, scope: CredentialIssuerScope, permission: str, now: datetime) -> ScopeAdmission:
    decision = evaluate_exact_issuer_scope(actor_user_id=actor, scope=scope, permission_key=permission, now=now)
    if not decision.allowed or decision.expires_at is None or decision.expires_at <= now:
        raise _deny()
    return decision


def require_issuer_source(
    scope: CredentialIssuerScope, deployment: DeploymentAuthority | None = None
) -> IntegrationInstance:
    """Lock exact canonical source; revocation can omit deployment evidence."""
    source = db.session.get(IntegrationInstance, scope.instance_id, with_for_update=True, populate_existing=True)
    if source is None or source.integration_type != 'secrets_pki' or source.provider_key != scope.provider_key:
        raise _deny()
    if deployment is not None and source.provider_key == 'vault':
        # Do not read/decrypt the stored AppRole SecretID during issuer administration.
        row = db.session.execute(
            select(VaultInstance)
            .options(
                load_only(
                    VaultInstance.endpoint, VaultInstance.namespace, VaultInstance.kv2_mounts, VaultInstance.verify_ssl
                )
            )
            .where(VaultInstance.integration_instance_id == source.id)
            .with_for_update(of=VaultInstance)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if (
            row is None
            or row.verify_ssl is not True
            or row.endpoint.rstrip('/') != deployment.transit.endpoint
            or (row.namespace or '') != scope.provider_namespace
            or scope.mount not in (row.kv2_mounts or ())
        ):
            raise _deny()
    elif deployment is not None and source.provider_key == 'openbao':
        local = current_local_inventory_source(
            source, namespace=scope.provider_namespace, mount=scope.mount, lock=True
        )
        if (
            local is None
            or deployment.scope != scope
            or local.endpoint != deployment.transit.endpoint
            or local.cluster_id != deployment.transit.cluster_id
        ):
            raise _deny()
    return source


def _latest(scope: CredentialIssuerScope) -> SecretCredentialIssuerRevision | None:
    return db.session.execute(
        select(SecretCredentialIssuerRevision)
        .where(
            SecretCredentialIssuerRevision.integration_instance_id == scope.instance_id,
            SecretCredentialIssuerRevision.provider_namespace == scope.provider_namespace,
            SecretCredentialIssuerRevision.mount == scope.mount,
        )
        .order_by(SecretCredentialIssuerRevision.revision_number.desc())
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _history(key_digest: str) -> tuple[SecretCredentialIssuerRevision, ...]:
    return tuple(
        db.session.execute(
            select(SecretCredentialIssuerRevision)
            .where(SecretCredentialIssuerRevision.key_sha256 == key_digest)
            .order_by(SecretCredentialIssuerRevision.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        .scalars()
        .all()
    )


def _current_deployment(scope: CredentialIssuerScope, now: datetime) -> DeploymentAuthority:
    authority = resolve_deployment_authority(scope, now=now)
    if authority is None:
        raise _deny()
    return authority


def _observe(
    scope: CredentialIssuerScope, token: str, *, actor: int, permission: str
) -> tuple[DeploymentAuthority, TransitIssuerObservation]:
    # No provider request occurs under the protected writer's SQL locks.
    if db.session().in_transaction():
        raise _deny()
    try:
        begin_issuer_transaction()
        _scope_admission(actor, scope, permission, datetime.now(UTC))
        authority = _current_deployment(scope, datetime.now(UTC))
        expected_actor = authority.source_owner_id if permission == _REQUEST else authority.checker_id
        if actor != expected_actor:
            raise _deny()
        require_issuer_source(scope, authority)
    finally:
        db.session.rollback()
    observation = observe_transit_issuer(authority.transit, token=token)
    return authority, observation


def _revalidate(
    authority: DeploymentAuthority, observation: TransitIssuerObservation, now: datetime
) -> DeploymentAuthority:
    current = _current_deployment(authority.scope, now)
    if (
        current != authority
        or observation.binding != current.transit
        or not _digest(observation.public_key_hex)
        or sha256(bytes.fromhex(observation.public_key_hex)).hexdigest() != current.transit.key_sha256
        or not timedelta(0) <= now - observation.observed_at <= _OBSERVATION_AGE
    ):
        raise _deny()
    return current


def _evidence(*refs: str) -> str:
    return sha256(canonical_statement({'schema': 'kaori.secrets.issuer_audit.v1', 'refs': list(refs)})).hexdigest()


def _grant_ref(grant: ScopeAdmission) -> str:
    return sha256(
        canonical_statement({'policy': grant.policy_ref, 'revision': grant.revision, 'actor': grant.actor_id})
    ).hexdigest()


def _revision(
    scope: CredentialIssuerScope,
    *,
    latest: SecretCredentialIssuerRevision | None,
    actor: int,
    state: str,
    now: datetime,
) -> SecretCredentialIssuerRevision:
    row = SecretCredentialIssuerRevision()
    row.integration_instance_id = scope.instance_id
    row.provider_key = scope.provider_key
    row.provider_namespace = scope.provider_namespace
    row.mount = scope.mount
    row.deployment_ref = scope.deployment_ref
    row.revision_number = 1 if latest is None else latest.revision_number + 1
    row.lifecycle_status = state
    row.algorithm = 'ed25519'
    row.recorded_by_user_id = actor
    row.recorded_at = now
    if latest is not None and state != 'draft':
        row.public_key_hex = latest.public_key_hex
        row.key_sha256 = latest.key_sha256
        row.requested_by_user_id = latest.requested_by_user_id
        row.effective_from = latest.effective_from
        row.effective_until = latest.effective_until
        row.approved_by_user_id = actor
        row.approved_at = now
    return row


def _append(
    source: IntegrationInstance,
    latest: SecretCredentialIssuerRevision | None,
    row: SecretCredentialIssuerRevision,
    expected_revision: int,
    now: datetime,
) -> None:
    if not issuer_transition_shape_qualified(
        source=source,
        latest=latest,
        candidate=row,
        expected_revision=expected_revision,
        current_deployment_ref=row.deployment_ref,
        key_history=_history(row.key_sha256),
        now=now,
    ):
        raise _deny()
    db.session.add(row)


def _audit(row: SecretCredentialIssuerRevision, grant: ScopeAdmission) -> None:
    db.session.flush()
    stage_operational_activity(
        user_id=row.recorded_by_user_id,
        event_type=f'secrets_pki_issuer_{row.lifecycle_status}',
        status='success',
        title='Credential Issuer Lifecycle Recorded',
        message='A governed issuer lifecycle revision was recorded.',
        metadata={
            'actor_user_id': row.recorded_by_user_id,
            'integration_instance_id': row.integration_instance_id,
            'issuer_revision': row.revision_number,
            'issuer_record_id': row.id,
            'policy_ref': grant.policy_ref,
            'policy_revision': grant.revision,
            'evidence_ref': row.evidence_ref,
            'lifecycle_status': row.lifecycle_status,
        },
    )


def _challenge(scope: CredentialIssuerScope, row: SecretCredentialIssuerChallenge) -> IssuerPossessionChallenge:
    return IssuerPossessionChallenge(
        IssuerResolutionTarget(
            scope.instance_id,
            scope.provider_key,
            scope.provider_namespace,
            scope.mount,
            scope.deployment_ref,
            row.revision_number,
        ),
        row.key_sha256,
        row.challenge_sha256,
        row.source_owner_id,
        row.issued_at,
        row.expires_at,
    )


def _new_challenge(
    scope: CredentialIssuerScope, draft: SecretCredentialIssuerRevision, now: datetime
) -> IssuedChallenge:
    challenge = SecretCredentialIssuerChallenge()
    challenge.integration_instance_id = scope.instance_id
    challenge.provider_key = scope.provider_key
    challenge.provider_namespace = scope.provider_namespace
    challenge.mount = scope.mount
    challenge.deployment_ref = scope.deployment_ref
    challenge.revision_number = draft.revision_number + 1
    challenge.key_sha256 = draft.key_sha256
    challenge.challenge_sha256 = sha256(token_bytes(32)).hexdigest()
    challenge.source_owner_id = draft.requested_by_user_id
    challenge.issued_at = now
    challenge.expires_at = min(now + _CHALLENGE_LIFETIME, draft.effective_until)
    challenge.lifecycle_status = 'pending'
    statement = issuer_possession_statement(_challenge(scope, challenge))
    if statement is None:
        raise _deny()
    db.session.add(challenge)
    return IssuedChallenge(challenge.challenge_sha256, statement, challenge.expires_at, draft.revision_number)


def request_issuer_enrollment(
    *, actor_id: int, intent: IssuerEnrollmentIntent, inspection_token: str
) -> IssuedChallenge:
    """Append draft and issue its one-time approval challenge in one audit transaction."""
    committed = False
    try:
        if not isinstance(intent, IssuerEnrollmentIntent) or not isinstance(intent.scope, CredentialIssuerScope):
            raise _deny()
        authority, observation = _observe(intent.scope, inspection_token, actor=actor_id, permission=_REQUEST)
        begin_issuer_transaction()
        now = datetime.now(UTC)
        grant = _scope_admission(actor_id, intent.scope, _REQUEST, now)
        now = datetime.now(UTC)
        authority = _revalidate(authority, observation, now)
        source = require_issuer_source(intent.scope, authority)
        if (
            authority.source_owner_id != actor_id
            or type(intent.expected_revision) is not int
            or intent.expected_revision < 0
            or not isinstance(intent.effective_until, datetime)
            or intent.effective_until.utcoffset() is None
            or not now < intent.effective_until <= authority.expires_at
            or grant.expires_at is None
            or grant.expires_at <= now
        ):
            raise _deny()
        latest = _latest(intent.scope)
        now = datetime.now(UTC)
        authority = _revalidate(authority, observation, now)
        if grant.expires_at is None or grant.expires_at <= now or intent.effective_until <= now:
            raise _deny()
        draft = _revision(intent.scope, latest=latest, actor=actor_id, state='draft', now=now)
        draft.public_key_hex = observation.public_key_hex
        draft.key_sha256 = authority.transit.key_sha256
        draft.requested_by_user_id = actor_id
        draft.effective_from = now
        draft.effective_until = intent.effective_until
        draft.evidence_ref = _evidence(authority.evidence_ref, _grant_ref(grant))
        _append(source, latest, draft, intent.expected_revision, now)
        current = datetime.now(UTC)
        _revalidate(authority, observation, current)
        if min(grant.expires_at, draft.effective_until) <= current:
            raise _deny()
        issued = _new_challenge(intent.scope, draft, now)
        _audit(draft, grant)
        db.session.commit()
        committed = True
        return issued
    except (SQLAlchemyError, ValueError, TypeError, AttributeError, RuntimeError):
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()


def _locked_challenge(intent: IssuerApprovalIntent) -> SecretCredentialIssuerChallenge:
    row = db.session.execute(
        select(SecretCredentialIssuerChallenge)
        .where(SecretCredentialIssuerChallenge.challenge_sha256 == intent.challenge_sha256)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    scope = intent.scope
    if (
        row is None
        or row.lifecycle_status != 'pending'
        or row.integration_instance_id != scope.instance_id
        or row.provider_key != scope.provider_key
        or row.provider_namespace != scope.provider_namespace
        or row.mount != scope.mount
        or row.deployment_ref != scope.deployment_ref
        or row.revision_number != intent.expected_revision + 1
    ):
        raise _deny()
    return row


def _approve_challenge(
    intent: IssuerApprovalIntent,
    authority: DeploymentAuthority,
    observation: TransitIssuerObservation,
    now: datetime,
) -> tuple[SecretCredentialIssuerChallenge, str, str]:
    row = _locked_challenge(intent)
    expected = _challenge(intent.scope, row)
    custody = resolve_custody_authority(expected, checker_id=authority.checker_id, observation=observation, now=now)
    signature = decode_transit_signature(intent.signature, key_version=authority.transit.key_version)
    if (
        custody is None
        or custody.deployment != authority
        or signature is None
        or not verify_issuer_possession(
            expected,
            signature=signature,
            verification_key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(observation.public_key_hex)),
            now=now,
        )
    ):
        raise _deny()
    possession = sha256(signature).hexdigest()
    row.lifecycle_status = 'consumed'
    row.resolved_at = now
    row.resolved_by_user_id = authority.checker_id
    row.possession_evidence_ref = possession
    return row, custody.evidence_ref, possession


def approve_issuer_enrollment(*, actor_id: int, intent: IssuerApprovalIntent, inspection_token: str) -> int:
    committed = False
    try:
        if (
            not isinstance(intent, IssuerApprovalIntent)
            or not isinstance(intent.scope, CredentialIssuerScope)
            or not _digest(intent.challenge_sha256)
            or type(intent.expected_revision) is not int
            or intent.expected_revision <= 0
        ):
            raise _deny()
        authority, observation = _observe(intent.scope, inspection_token, actor=actor_id, permission=_APPROVE)
        begin_issuer_transaction()
        now = datetime.now(UTC)
        grant = _scope_admission(actor_id, intent.scope, _APPROVE, now)
        owner_grant = _scope_admission(authority.source_owner_id, intent.scope, _REQUEST, now)
        now = datetime.now(UTC)
        authority = _revalidate(authority, observation, now)
        source = require_issuer_source(intent.scope, authority)
        latest = _latest(intent.scope)
        if (
            latest is None
            or latest.lifecycle_status != 'draft'
            or latest.revision_number != intent.expected_revision
            or latest.requested_by_user_id != authority.source_owner_id
            or actor_id != authority.checker_id
            or latest.key_sha256 != authority.transit.key_sha256
            or latest.effective_until > authority.expires_at
            or grant.expires_at is None
            or owner_grant.expires_at is None
            or min(grant.expires_at, owner_grant.expires_at) <= now
        ):
            raise _deny()
        now = datetime.now(UTC)
        authority = _revalidate(authority, observation, now)
        if min(grant.expires_at, owner_grant.expires_at) <= now or latest.effective_until <= now:
            raise _deny()
        challenge, custody_ref, possession_ref = _approve_challenge(intent, authority, observation, now)
        if challenge.key_sha256 != latest.key_sha256 or challenge.source_owner_id != latest.requested_by_user_id:
            raise _deny()
        active = _revision(intent.scope, latest=latest, actor=actor_id, state='active', now=now)
        active.evidence_ref = _evidence(
            authority.evidence_ref, custody_ref, possession_ref, _grant_ref(grant), _grant_ref(owner_grant)
        )
        _append(source, latest, active, intent.expected_revision, now)
        current = datetime.now(UTC)
        _revalidate(authority, observation, current)
        custody = resolve_custody_authority(
            _challenge(intent.scope, challenge), checker_id=actor_id, observation=observation, now=current
        )
        if (
            custody is None
            or custody.deployment != authority
            or custody.evidence_ref != custody_ref
            or min(grant.expires_at, owner_grant.expires_at, active.effective_until) <= current
        ):
            raise _deny()
        _audit(active, grant)
        revision = active.revision_number
        db.session.commit()
        committed = True
        return revision
    except (SQLAlchemyError, ValueError, TypeError, AttributeError, RuntimeError):
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()


def _revoke_pending(row: SecretCredentialIssuerRevision, now: datetime) -> None:
    challenges = (
        db.session.execute(
            select(SecretCredentialIssuerChallenge)
            .where(
                SecretCredentialIssuerChallenge.integration_instance_id == row.integration_instance_id,
                SecretCredentialIssuerChallenge.provider_key == row.provider_key,
                SecretCredentialIssuerChallenge.provider_namespace == row.provider_namespace,
                SecretCredentialIssuerChallenge.mount == row.mount,
                SecretCredentialIssuerChallenge.deployment_ref == row.deployment_ref,
                SecretCredentialIssuerChallenge.key_sha256 == row.key_sha256,
                SecretCredentialIssuerChallenge.revision_number == row.revision_number,
                SecretCredentialIssuerChallenge.lifecycle_status == 'pending',
            )
            .order_by(SecretCredentialIssuerChallenge.id)
            .with_for_update()
        )
        .scalars()
        .all()
    )
    for challenge in challenges:
        challenge.lifecycle_status = 'revoked'
        challenge.resolved_at = now
        challenge.resolved_by_user_id = row.recorded_by_user_id


def revoke_issuer_enrollment(*, actor_id: int, scope: CredentialIssuerScope, expected_revision: int) -> int:
    """Same-binding immediate revocation, including expired or unavailable provider."""
    committed = False
    try:
        begin_issuer_transaction()
        now = datetime.now(UTC)
        grant = _scope_admission(actor_id, scope, _REVOKE, now)
        source = require_issuer_source(scope)
        latest = _latest(scope)
        now = datetime.now(UTC)
        if (
            latest is None
            or latest.provider_key != scope.provider_key
            or latest.deployment_ref != scope.deployment_ref
            or grant.expires_at is None
            or grant.expires_at <= now
        ):
            raise _deny()
        revoked = _revision(scope, latest=latest, actor=actor_id, state='revoked', now=now)
        revoked.evidence_ref = _evidence(latest.evidence_ref, _grant_ref(grant))
        _append(source, latest, revoked, expected_revision, now)
        _revoke_pending(revoked, now)
        _audit(revoked, grant)
        revision = revoked.revision_number
        db.session.commit()
        committed = True
        return revision
    except (SQLAlchemyError, ValueError, TypeError, AttributeError, RuntimeError):
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()
