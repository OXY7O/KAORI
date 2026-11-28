"""Create-only, audited host credential reference candidates (#5162).

The authenticated application caller must supply its own actor identity.
No material-use permission, provider request, SSH or public route is granted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import load_only

from app.access.scope_policy import evaluate_exact_openbao_scope, evaluate_exact_vault_scope
from app.extensions.db import db
from app.infrastructure_automation.host_access_reference import (
    HostAccessReferenceReview,
    assess_scoped_host_access_references,
)
from app.infrastructure_automation.host_enrollment import get_scoped_host_assignment, host_revision
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import (
    local_inventory_deployment_ref,
)
from app.models.automation import AutomationHostAccessBinding
from app.models.integration import IntegrationInstance
from app.models.scope_access import ScopeAccessPolicy
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.user import User
from app.platform_operations.notifications.service import stage_operational_activity

_REQUIRED_PERMISSIONS = frozenset({'integrations.manage', 'inventory.view', 'secrets_pki.view'})
_DIGEST = re.compile(r'[a-f0-9]{64}\Z')
_KEY_DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')
_MAX_RECORDS = 200


@dataclass(frozen=True, slots=True, repr=False)
class HostAccessBindingIntent:
    connection_id: int
    host_id: str
    expected_host_revision: str
    scope_ref: str
    secret_identity_id: str
    expected_secret_version: int
    host_key_digest: str


class HostAccessBindingDenied(ValueError):
    """Generic denial without reference existence or provider detail."""


def _deny() -> HostAccessBindingDenied:
    return HostAccessBindingDenied(
        'Host access reference could not be recorded. Review the approved scope and inventory.'
    )


def _canonical_uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except (TypeError, ValueError, AttributeError):
        return False


def _valid_intent(intent: HostAccessBindingIntent, actor_id: int) -> bool:
    return (
        type(actor_id) is int
        and actor_id > 0
        and type(intent.connection_id) is int
        and intent.connection_id > 0
        and type(intent.expected_secret_version) is int
        and intent.expected_secret_version > 0
        and all(_canonical_uuid(value) for value in (intent.host_id, intent.scope_ref, intent.secret_identity_id))
        and isinstance(intent.expected_host_revision, str)
        and _DIGEST.fullmatch(intent.expected_host_revision) is not None
        and isinstance(intent.host_key_digest, str)
        and _KEY_DIGEST.fullmatch(intent.host_key_digest) is not None
    )


def _require_actor(actor_id: int) -> None:
    actor = db.session.get(User, actor_id)
    if (
        actor is None
        or not actor.is_active
        or actor.role_record is None
        or not actor.role_record.is_active
        or not _REQUIRED_PERMISSIONS.issubset(actor.role_record.permission_keys())
    ):
        raise _deny()


def _require_scope(actor_id: int, scope_ref: str, instant: datetime) -> ScopeAccessPolicy:
    policy = db.session.get(ScopeAccessPolicy, scope_ref)
    if (
        policy is None
        or policy.principal_user_id != actor_id
        or policy.permission_key != 'secrets_pki.view'
        or policy.scope_level not in ('vault_mount', 'openbao_mount')
        or not isinstance(policy.provider_namespace, str)
        or not isinstance(policy.mount, str)
    ):
        raise _deny()
    evaluator = evaluate_exact_openbao_scope if policy.scope_level == 'openbao_mount' else evaluate_exact_vault_scope
    admission = evaluator(
        actor_user_id=actor_id,
        instance_id=policy.integration_instance_id,
        provider_namespace=policy.provider_namespace,
        mount=policy.mount,
        now=instant,
        lock_for_read=True,
    )
    if (
        not admission.allowed
        or admission.policy_ref != policy.id
        or admission.revision != policy.current_revision
        or admission.expires_at is None
        or admission.expires_at <= instant
    ):
        raise _deny()
    return policy


def _locked_collection(policy: ScopeAccessPolicy) -> SecretInventoryCollectionState:
    collection = (
        SecretInventoryCollectionState.query.filter_by(
            integration_instance_id=policy.integration_instance_id,
            provider_namespace=policy.provider_namespace,
            mount=policy.mount,
        )
        .with_for_update()
        .one_or_none()
    )
    if (
        collection is None
        or collection.status != 'ready'
        or type(collection.observed_count) is not int
        or not 1 <= collection.observed_count <= _MAX_RECORDS
    ):
        raise _deny()
    return collection


def _selected_representation(
    policy: ScopeAccessPolicy, collection: SecretInventoryCollectionState, secret_identity_id: str
) -> SecretProviderRepresentation:
    rows = (
        SecretProviderRepresentation.query.options(
            load_only(
                SecretProviderRepresentation.id,
                SecretProviderRepresentation.secret_identity_id,
                SecretProviderRepresentation.integration_instance_id,
                SecretProviderRepresentation.provider_key,
                SecretProviderRepresentation.provider_namespace,
                SecretProviderRepresentation.mount,
                SecretProviderRepresentation.path_sha256,
                SecretProviderRepresentation.representation_role,
                SecretProviderRepresentation.observation_status,
                SecretProviderRepresentation.current_version,
                SecretProviderRepresentation.last_observed_at,
            )
        )
        .filter_by(
            integration_instance_id=policy.integration_instance_id,
            provider_namespace=policy.provider_namespace,
            mount=policy.mount,
            provider_key='openbao' if policy.scope_level == 'openbao_mount' else 'vault',
            representation_role='material_authority',
            observation_status='observed',
        )
        .order_by(SecretProviderRepresentation.id.asc())
        .limit(_MAX_RECORDS + 1)
        .with_for_update()
        .all()
    )
    if len(rows) != collection.observed_count or any(
        row.last_observed_at != collection.last_observed_at for row in rows
    ):
        raise _deny()
    selected = [row for row in rows if row.secret_identity_id == secret_identity_id]
    if len(selected) != 1:
        raise _deny()
    return selected[0]


def _selected_version(representation: SecretProviderRepresentation, expected_version: int) -> SecretVersionObservation:
    if representation.current_version != expected_version:
        raise _deny()
    version = (
        SecretVersionObservation.query.filter_by(representation_id=representation.id, version=expected_version)
        .with_for_update()
        .one_or_none()
    )
    if version is None:
        raise _deny()
    return version


def record_host_access_reference(*, actor_id: int, intent: HostAccessBindingIntent) -> HostAccessReferenceReview:
    """Own the transaction: verify canonical scope, stage audit, commit or deny.

    Create-only metadata selection; no replacement, grant, secret-use policy
    or trusted host-key verification. No HTTP caller is enabled in this slice.
    """
    committed = False
    try:
        if not _valid_intent(intent, actor_id):
            raise _deny()
        _require_actor(actor_id)
        instant = datetime.now(UTC)
        policy = _require_scope(actor_id, intent.scope_ref, instant)
        connection = db.session.get(IntegrationInstance, intent.connection_id, with_for_update=True)
        assignment = get_scoped_host_assignment(intent.connection_id, intent.host_id, lock=True)
        if connection is None or assignment is None or host_revision(assignment) != intent.expected_host_revision:
            raise _deny()
        if db.session.get(AutomationHostAccessBinding, assignment.id) is not None:
            raise _deny()
        provider = db.session.get(IntegrationInstance, policy.integration_instance_id, with_for_update=True)
        if provider is None:
            raise _deny()
        collection = _locked_collection(policy)
        representation = _selected_representation(policy, collection, intent.secret_identity_id)
        version = _selected_version(representation, intent.expected_secret_version)
        identity = db.session.get(SecretIdentity, representation.secret_identity_id, with_for_update=True)
        if identity is None:
            raise _deny()
        deployment_ref = None
        if policy.scope_level == 'openbao_mount':
            deployment_ref = local_inventory_deployment_ref(
                provider, namespace=representation.provider_namespace, mount=representation.mount, lock=True
            )
            if deployment_ref is None:
                raise _deny()
        review = assess_scoped_host_access_references(
            connection=connection,
            assignment=assignment,
            provider=provider,
            representation=representation,
            collection=collection,
            version=version,
            host_key_digest=intent.host_key_digest,
            now=instant,
            provider_deployment_ref=deployment_ref,
        )
        if review.state != 'references_recorded' or review.fingerprint is None:
            raise _deny()
        binding = AutomationHostAccessBinding()
        binding.assignment_id = assignment.id
        binding.secret_representation_id = representation.id
        binding.secret_version = version.version
        binding.host_revision = intent.expected_host_revision
        binding.reference_fingerprint = review.fingerprint
        binding.host_key_digest = intent.host_key_digest
        binding.recorded_by_user_id = actor_id
        binding.recorded_at = instant
        db.session.add(binding)
        stage_operational_activity(
            user_id=actor_id,
            event_type='automation_host_access_reference_recorded',
            status='success',
            title='Host Access Reference Recorded',
            message='A metadata-only reference candidate was recorded. SSH trust and execution remain blocked.',
            metadata={
                'actor_user_id': actor_id,
                'policy_ref': policy.id,
                'policy_revision': policy.current_revision,
                'integration_instance_id': connection.id,
                'assignment_id': assignment.id,
                'reference_fingerprint': review.fingerprint,
                'execution_authorized': False,
            },
        )
        db.session.commit()
        committed = True
        return review
    except (SQLAlchemyError, ValueError, TypeError, AttributeError, RuntimeError):
        raise _deny() from None
    finally:
        if not committed:
            db.session.rollback()
