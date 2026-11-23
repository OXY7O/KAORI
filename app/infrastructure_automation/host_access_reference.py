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
from typing import Any

from app.infrastructure_automation.kubernetes.source_policy import committed_source_state
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretIdentity, SecretProviderRepresentation

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
    if (
        not isinstance(connection, IntegrationInstance)
        or type(connection.id) is not int
        or connection.id <= 0
        or not connection.enabled
        or connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or connection.lifecycle_status != 'active'
        or connection.environment not in _NON_PRODUCTION
    ):
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
    if (
        not isinstance(representation, SecretProviderRepresentation)
        or type(representation.id) is not int
        or representation.id <= 0
        or representation.secret_identity_id != secret_identity.id
        or type(representation.integration_instance_id) is not int
        or representation.integration_instance_id <= 0
        or representation.provider_key != 'vault'
        or representation.representation_role != 'material_authority'
        or representation.observation_status != 'observed'
        or type(representation.current_version) is not int
        or representation.current_version <= 0
        or type(representation.path_sha256) is not str
        or _HEX_DIGEST.fullmatch(representation.path_sha256) is None
    ):
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
