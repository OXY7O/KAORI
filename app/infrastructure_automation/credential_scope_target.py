"""Exact committed target resolution for governed credential grants (#5184).

This resolver is non-authorizing: a current metadata match does not establish
credential type, grant approval, independent SSH trust or worker admission.
The caller owns the transaction, authorization and mandatory audit.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import joinedload, load_only

from app.extensions.db import db
from app.infrastructure_automation.host_access_reference import assess_bound_host_access_references
from app.infrastructure_automation.host_enrollment import get_scoped_host_assignment
from app.infrastructure_automation.kubernetes.source_policy import PROFILE_KEY, SOURCE_CANDIDATE_SHA
from app.models.automation import AutomationHostAccessBinding
from app.models.integration import IntegrationInstance
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy
from app.models.secrets_pki import (
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.vault import VaultInstance

# A fixed reviewed source artifact, not a caller-selected command or path.
READ_ONLY_FACTS_OPERATION = 'ansible/playbooks/linux_host_facts.yml'
CREDENTIAL_USE_PERMISSION = 'secrets_pki.use_automation_credential'


def exact_credential_target_current(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> bool:
    """Requalify one persisted selector against locked canonical reference evidence.

    Call only inside the governed transaction after locking the policy row.
    Missing, changed or unqualified records return false; database errors
    propagate to the transaction owner for rollback, never to an execution path.
    """
    if (
        now.utcoffset() is None
        or policy.id != target.policy_id
        or policy.scope_level != 'automation_credential'
        or policy.permission_key != CREDENTIAL_USE_PERMISSION
        or target.profile_key != PROFILE_KEY
        or target.source_revision != SOURCE_CANDIDATE_SHA
        or target.operation_key != READ_ONLY_FACTS_OPERATION
    ):
        return False
    connection = db.session.get(
        IntegrationInstance, target.ansible_connection_id, populate_existing=True, with_for_update=True
    )
    assignment = get_scoped_host_assignment(target.ansible_connection_id, target.host_id, lock=True)
    if connection is None or assignment is None or assignment.id != target.assignment_id:
        return False
    binding = db.session.get(
        AutomationHostAccessBinding, assignment.id, populate_existing=True, with_for_update=True
    )
    if (
        binding is None
        or binding.secret_representation_id != target.secret_representation_id
        or binding.secret_version != target.secret_version
        or binding.host_revision != target.host_revision
        or binding.reference_fingerprint != target.reference_fingerprint
    ):
        return False
    representation = db.session.get(
        SecretProviderRepresentation,
        target.secret_representation_id,
        populate_existing=True,
        options=[
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
            ),
            joinedload(SecretProviderRepresentation.secret_identity),
        ],
    )
    if (
        representation is None
        or representation.secret_identity_id != target.secret_identity_id
        or representation.integration_instance_id != policy.integration_instance_id
        or representation.provider_namespace != policy.provider_namespace
        or representation.mount != policy.mount
    ):
        return False
    provider = db.session.get(
        IntegrationInstance, policy.integration_instance_id, populate_existing=True, with_for_update=True
    )
    vault = VaultInstance.query.filter_by(integration_instance_id=policy.integration_instance_id).first()
    if (
        provider is None
        or vault is None
        or (vault.namespace or '') != policy.provider_namespace
        or policy.mount not in (vault.kv2_mounts or [])
    ):
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
    version = (
        SecretVersionObservation.query.filter_by(
            representation_id=target.secret_representation_id, version=target.secret_version
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if collection is None or version is None:
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
    )
    return review.state == 'references_recorded' and review.fingerprint == target.reference_fingerprint
