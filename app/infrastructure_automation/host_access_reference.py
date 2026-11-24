"""Non-executable host access reference projection (#5162).

Consumes only committed IntegrationInstance and Secrets & PKI metadata.
An observed secret identity and a pinned host-key digest are *references*,
not remote SSH trust, worker attestation, privilege proof or authorization.
The provider/worker remains authoritative for those independent facts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.infrastructure_automation.kubernetes.source_policy import committed_source_state
from app.models.automation import AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)

_HOST_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z')
_HEX_DIGEST = re.compile(r'[a-f0-9]{64}\Z')
_EE_DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')
_NON_PRODUCTION = frozenset(
    {'development', 'testing', 'staging', 'laboratory', 'sandbox', 'proof_of_concept', 'non_production'}
)


@dataclass(frozen=True, slots=True)
class HostAccessReferenceReview:
    """Safe operator projection, never an execution-capability assertion."""

    state: str
    reason_code: str
    fingerprint: str | None
    credential_reference_recorded: bool
    host_key_reference_recorded: bool
    ssh_trust_verified: bool = False
    privileged_identity_verified: bool = False
    execution_authorized: bool = False

    def committed_summary(self) -> dict[str, Any]:
        """Do not commit host IDs, addresses, Vault paths or key material."""
        return {
            'schema_version': 1,
            'state': self.state,
            'reason_code': self.reason_code,
            'fingerprint': self.fingerprint,
            'credential_reference_recorded': self.credential_reference_recorded,
            'host_key_reference_recorded': self.host_key_reference_recorded,
            'ssh_trust_verified': False,
            'privileged_identity_verified': False,
            'execution_authorized': False,
        }


def _blocked(reason: str) -> HostAccessReferenceReview:
    return HostAccessReferenceReview('blocked', reason, None, False, False)


def _eligible_ansible_connection(connection: object) -> bool:
    return (
        isinstance(connection, IntegrationInstance)
        and type(connection.id) is int
        and connection.id > 0
        and connection.enabled
        and connection.integration_type == 'configuration_automation'
        and connection.provider_key == 'ansible'
        and connection.lifecycle_status == 'active'
        and connection.environment in _NON_PRODUCTION
    )


def _qualified_secret_representation(
    secret_identity: SecretIdentity,
    representation: object,
) -> bool:
    return (
        isinstance(representation, SecretProviderRepresentation)
        and type(representation.id) is int
        and representation.id > 0
        and representation.secret_identity_id == secret_identity.id
        and type(representation.integration_instance_id) is int
        and representation.integration_instance_id > 0
        and representation.provider_key == 'vault'
        and representation.representation_role == 'material_authority'
        and representation.observation_status == 'observed'
        and type(representation.current_version) is int
        and representation.current_version > 0
        and type(representation.path_sha256) is str
        and _HEX_DIGEST.fullmatch(representation.path_sha256) is not None
    )


def assess_host_access_references(
    *,
    connection: IntegrationInstance,
    host_asset_id: str,
    secret_identity: SecretIdentity | None,
    secret_representation: SecretProviderRepresentation | None,
    host_key_digest: str | None,
) -> HostAccessReferenceReview:
    """Interpret canonical committed references without reading secrets or probing SSH.

    A caller must first enforce its normal RBAC and asset/tenant scope. This
    pure function is never an HTTP action, signed proof, or target allowance.
    """
    if not _eligible_ansible_connection(connection):
        return _blocked('ANSIBLE_CONNECTION_SCOPE_UNQUALIFIED')
    metadata = connection.metadata_json if type(connection.metadata_json) is dict else {}
    if committed_source_state(metadata) != 'checked':
        return _blocked('IMMUTABLE_SOURCE_NOT_QUALIFIED')
    ee_digest = metadata.get('execution_environment_digest')
    if type(ee_digest) is not str or _EE_DIGEST.fullmatch(ee_digest) is None:
        return _blocked('EXECUTION_ENVIRONMENT_REFERENCE_UNQUALIFIED')
    if type(host_asset_id) is not str or _HOST_ID.fullmatch(host_asset_id) is None:
        return _blocked('HOST_ASSET_IDENTITY_UNQUALIFIED')
    if (
        not isinstance(secret_identity, SecretIdentity)
        or not isinstance(secret_identity.id, str)
        or not secret_identity.id
        or secret_identity.lifecycle_status != 'discovered'
    ):
        return _blocked('SECRET_IDENTITY_NOT_OBSERVED')
    representation = secret_representation
    if not isinstance(representation, SecretProviderRepresentation):
        return _blocked('SECRET_PROVIDER_REFERENCE_UNQUALIFIED')
    if not _qualified_secret_representation(secret_identity, representation):
        return _blocked('SECRET_PROVIDER_REFERENCE_UNQUALIFIED')
    if type(host_key_digest) is not str or _EE_DIGEST.fullmatch(host_key_digest) is None:
        return _blocked('HOST_KEY_REFERENCE_UNQUALIFIED')

    material = {
        'schema_version': 1,
        'ansible_connection_id': connection.id,
        'environment': connection.environment,
        'host_asset_id': host_asset_id,
        'secret_identity_id': secret_identity.id,
        'secret_provider_id': representation.integration_instance_id,
        'secret_representation_id': representation.id,
        'secret_version': representation.current_version,
        'secret_path_digest': representation.path_sha256,
        'host_key_digest': host_key_digest,
        'source_sha': metadata.get('source_sha'),
        'execution_environment_digest': ee_digest,
    }
    fingerprint = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    return HostAccessReferenceReview(
        'references_recorded',
        'INDEPENDENT_SSH_TRUST_AND_PRIVILEGE_EVIDENCE_REQUIRED',
        fingerprint,
        True,
        True,
    )


def _current_membership(connection: IntegrationInstance, assignment: AutomationInventoryAssignment) -> bool:
    host = assignment.host
    return (
        assignment.integration_instance_id == connection.id
        and assignment.enabled is True
        and host is not None
        and assignment.host_id == host.id
        and host.lifecycle_status == 'registered'
        and host.environment == connection.environment
        and assignment.role in {'control_plane', 'worker'}
    )


def _matching_vault_source(
    connection: IntegrationInstance, provider: IntegrationInstance, representation: SecretProviderRepresentation
) -> bool:
    return (
        provider.id == representation.integration_instance_id
        and provider.integration_type == 'secrets_pki'
        and provider.provider_key == 'vault'
        and provider.enabled is True
        and provider.lifecycle_status == 'active'
        and provider.readiness_status == 'ready'
        and provider.environment == connection.environment
    )


def _fresh_observation(value: datetime | None, now: datetime) -> bool:
    return (
        isinstance(value, datetime)
        and value.utcoffset() is not None
        and now.utcoffset() is not None
        and timedelta(0) <= now - value <= timedelta(hours=24)
    )


def _current_collection(
    representation: SecretProviderRepresentation, collection: SecretInventoryCollectionState, now: datetime
) -> bool:
    return (
        collection.integration_instance_id == representation.integration_instance_id
        and collection.provider_namespace == representation.provider_namespace
        and collection.mount == representation.mount
        and collection.status == 'ready'
        and type(collection.observed_count) is int
        and 0 < collection.observed_count <= 200
        and _fresh_observation(collection.last_observed_at, now)
        and _fresh_observation(collection.last_committed_at, now)
        and collection.last_observed_at == representation.last_observed_at
    )


def _current_secret_version(
    representation: SecretProviderRepresentation, version: SecretVersionObservation, now: datetime
) -> bool:
    return (
        version.representation_id == representation.id
        and version.version == representation.current_version
        and version.last_observed_at == representation.last_observed_at
        and _fresh_observation(version.last_observed_at, now)
        and version.destroyed is False
        # Require absence of any deletion intent; no cross-domain classifier import.
        and version.provider_deletion_time in (None, '')
    )


def assess_scoped_host_access_references(
    *,
    connection: IntegrationInstance,
    assignment: AutomationInventoryAssignment,
    provider: IntegrationInstance,
    representation: SecretProviderRepresentation,
    collection: SecretInventoryCollectionState,
    version: SecretVersionObservation,
    host_key_digest: str | None,
    now: datetime,
) -> HostAccessReferenceReview:
    """Qualify reference metadata only, after caller-enforced exact resource policy.

    Inputs must come from authorized canonical committed reads. This does not
    replace the audited #724 policy evaluator, prove secret type or authorize
    material access, and must not be exposed as a browser-supplied decision.
    """
    if not _current_membership(connection, assignment):
        return _blocked('HOST_MEMBERSHIP_UNQUALIFIED')
    if not _matching_vault_source(connection, provider, representation):
        return _blocked('SECRET_SOURCE_SCOPE_UNQUALIFIED')
    if not _current_collection(representation, collection, now):
        return _blocked('SECRET_COLLECTION_UNQUALIFIED')
    if not _current_secret_version(representation, version, now):
        return _blocked('SECRET_VERSION_UNQUALIFIED')
    return assess_host_access_references(
        connection=connection,
        host_asset_id=assignment.host_id,
        secret_identity=representation.secret_identity,
        secret_representation=representation,
        host_key_digest=host_key_digest,
    )
