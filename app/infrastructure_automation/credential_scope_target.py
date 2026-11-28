"""Exact committed target resolution for governed credential grants (#5184).

This resolver is non-authorizing: a current metadata match does not establish
credential type, grant approval, independent SSH trust or worker admission.
The caller owns the transaction, authorization and mandatory audit.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import load_only

from app.extensions.db import db
from app.infrastructure_automation.host_access_reference import assess_bound_host_access_references
from app.infrastructure_automation.host_enrollment import get_scoped_host_assignment
from app.infrastructure_automation.kubernetes.source_policy import PROFILE_KEY, SOURCE_CANDIDATE_SHA
from app.infrastructure_automation.remote_preflight_source import REMOTE_CANDIDATE_SHA, REMOTE_PLAYBOOK
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import (
    local_inventory_deployment_ref,
)
from app.models.automation import AutomationHostAccessBinding
from app.models.integration import IntegrationInstance
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.vault import VaultInstance

# A fixed reviewed source artifact, not a caller-selected command or path.
READ_ONLY_FACTS_OPERATION = 'ansible/playbooks/linux_host_facts.yml'
CREDENTIAL_USE_PERMISSION = 'secrets_pki.use_automation_credential'


def _current_representation(
    policy: ScopeAccessPolicy,
    target: AutomationCredentialScopeTarget,
    collection: SecretInventoryCollectionState | None,
    provider_key: str,
) -> SecretProviderRepresentation | None:
    """Lock a complete bounded generation and select one exact identity."""
    if (
        collection is None
        or collection.status != 'ready'
        or type(collection.observed_count) is not int
        or not 1 <= collection.observed_count <= 200
    ):
        return None
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
            provider_key=provider_key,
            representation_role='material_authority',
            observation_status='observed',
        )
        .order_by(SecretProviderRepresentation.id.asc())
        .limit(201)
        .populate_existing()
        .with_for_update()
        .all()
    )
    if len(rows) != collection.observed_count or any(
        row.last_observed_at != collection.last_observed_at for row in rows
    ):
        return None
    selected = [row for row in rows if row.secret_identity_id == target.secret_identity_id]
    if len(selected) != 1 or selected[0].id != target.secret_representation_id:
        return None
    return selected[0]


def exact_credential_target_current(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> bool:
    """Requalify one persisted selector against locked canonical reference evidence.

    Call only inside the governed transaction after locking the policy row.
    Missing, changed or unqualified records return false; database errors
    propagate to the transaction owner for rollback, never to an execution path.
    """
    if target.source_revision != SOURCE_CANDIDATE_SHA or target.operation_key != READ_ONLY_FACTS_OPERATION:
        return False
    return _exact_reference_current(policy, target, now=now)


def exact_remote_credential_draft_current(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> bool:
    """Candidate-only remote selector; never accepted by the active grant evaluator."""
    if target.source_revision != REMOTE_CANDIDATE_SHA or target.operation_key != REMOTE_PLAYBOOK:
        return False
    return _exact_reference_current(policy, target, now=now)


def _exact_reference_current(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> bool:
    if (
        now.utcoffset() is None
        or policy.id != target.policy_id
        or policy.scope_level != 'automation_credential'
        or policy.permission_key != CREDENTIAL_USE_PERMISSION
        or target.profile_key != PROFILE_KEY
    ):
        return False
    connection = db.session.get(
        IntegrationInstance, target.ansible_connection_id, populate_existing=True, with_for_update=True
    )
    assignment = get_scoped_host_assignment(target.ansible_connection_id, target.host_id, lock=True)
    if connection is None or assignment is None or assignment.id != target.assignment_id:
        return False
    db.session.refresh(assignment, with_for_update=True)
    binding = db.session.get(AutomationHostAccessBinding, assignment.id, populate_existing=True, with_for_update=True)
    if (
        binding is None
        or binding.secret_representation_id != target.secret_representation_id
        or binding.secret_version != target.secret_version
        or binding.host_revision != target.host_revision
        or binding.reference_fingerprint != target.reference_fingerprint
    ):
        return False
    provider = db.session.get(
        IntegrationInstance, policy.integration_instance_id, populate_existing=True, with_for_update=True
    )
    if provider is None or policy.provider_namespace is None or policy.mount is None:
        return False
    deployment_ref = None
    if provider.provider_key == 'vault':
        vault = (
            VaultInstance.query.options(load_only(VaultInstance.namespace, VaultInstance.kv2_mounts))
            .filter_by(integration_instance_id=policy.integration_instance_id)
            .populate_existing()
            .with_for_update(of=VaultInstance)
            .one_or_none()
        )
        if (
            vault is None
            or (vault.namespace or '') != policy.provider_namespace
            or policy.mount not in (vault.kv2_mounts or [])
        ):
            return False
    elif provider.provider_key == 'openbao':
        deployment_ref = local_inventory_deployment_ref(
            provider,
            namespace=policy.provider_namespace,
            mount=policy.mount,
            environment=connection.environment,
            lock=True,
        )
        if deployment_ref is None:
            return False
    else:
        return False
    collection = (
        SecretInventoryCollectionState.query.filter_by(
            integration_instance_id=policy.integration_instance_id,
            provider_namespace=policy.provider_namespace,
            mount=policy.mount,
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    representation = _current_representation(policy, target, collection, provider.provider_key)
    if representation is None or collection is None:
        return False
    version = (
        SecretVersionObservation.query.filter_by(
            representation_id=target.secret_representation_id, version=target.secret_version
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    identity = db.session.get(SecretIdentity, target.secret_identity_id, populate_existing=True, with_for_update=True)
    if version is None or identity is None:
        return False
    # Reuse the existing candidate classifier rather than creating a second
    # interpretation of host revision, source, EE and metadata freshness.
    review = assess_bound_host_access_references(
        binding=binding,
        connection=connection,
        assignment=assignment,
        provider=provider,
        representation=representation,
        collection=collection,
        version=version,
        now=now,
        provider_deployment_ref=deployment_ref,
    )
    return review.state == 'references_recorded' and review.fingerprint == target.reference_fingerprint
