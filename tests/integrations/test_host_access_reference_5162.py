"""#5162: secret inventory and host-key references must not grant SSH execution."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure_automation.host_access_reference import assess_host_access_references
from app.infrastructure_automation.kubernetes.kubespray_preflight import KUBESPRAY_RELEASE
from app.infrastructure_automation.kubernetes.source_policy import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretIdentity, SecretProviderRepresentation


def _evidence():
    metadata = {
        'source_repository': REPOSITORY,
        'source_sha': SOURCE_CANDIDATE_SHA,
        'profile_key': PROFILE_KEY,
        'ansible_core_version': ANSIBLE_CORE_VERSION,
        'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
        'kubespray_release': KUBESPRAY_RELEASE,
        'execution_environment_digest': 'sha256:' + 'b' * 64,
    }
    metadata['source_validation'] = {
        'status': 'source_checked',
        'repository': REPOSITORY,
        'revision': SOURCE_CANDIDATE_SHA,
        'profile_key': PROFILE_KEY,
        'checked_files': 5,
        'operation_authorized': False,
    }
    connection = IntegrationInstance(
        id=7,
        integration_type='configuration_automation',
        provider_key='ansible',
        adapter_key='ansible',
        name='lab-ansible',
        environment='laboratory',
        lifecycle_status='active',
        enabled=True,
        metadata_json=metadata,
    )
    identity = SecretIdentity(id=str(uuid4()), lifecycle_status='discovered')
    representation = SecretProviderRepresentation(
        id=17,
        secret_identity_id=identity.id,
        integration_instance_id=31,
        provider_key='vault',
        representation_role='material_authority',
        observation_status='observed',
        path_sha256='a' * 64,
        current_version=2,
    )
    return {
        'connection': connection,
        'host_asset_id': 'host-cp-01',
        'secret_identity': identity,
        'secret_representation': representation,
        'host_key_digest': 'sha256:' + 'e' * 64,
    }


def _review(**changes):
    fields = _evidence()
    fields.update(changes)
    return assess_host_access_references(**fields)


def test_qualified_reference_is_not_ssh_trust_or_run_approval():
    fields = _evidence()
    result = assess_host_access_references(**fields)
    assert result.state == 'references_recorded'
    assert result.fingerprint and len(result.fingerprint) == 64
    assert result.credential_reference_recorded
    assert result.host_key_reference_recorded
    assert result.ssh_trust_verified is False
    assert result.privileged_identity_verified is False
    assert result.execution_authorized is False
    committed = result.committed_summary()
    for private_value in (fields['host_asset_id'], fields['secret_identity'].id, 'vault', 'host-cp'):
        assert private_value not in str(committed)
    assert committed['execution_authorized'] is False


@pytest.mark.parametrize(
    ('attribute', 'value', 'reason'),
    [
        ('environment', 'production', 'ANSIBLE_CONNECTION_SCOPE_UNQUALIFIED'),
        ('provider_key', 'other', 'ANSIBLE_CONNECTION_SCOPE_UNQUALIFIED'),
        ('lifecycle_status', 'disabled', 'ANSIBLE_CONNECTION_SCOPE_UNQUALIFIED'),
        ('enabled', False, 'ANSIBLE_CONNECTION_SCOPE_UNQUALIFIED'),
        ('id', 0, 'ANSIBLE_CONNECTION_SCOPE_UNQUALIFIED'),
    ],
)
def test_invalid_ansible_connection_denied(attribute, value, reason):
    fields = _evidence()
    setattr(fields['connection'], attribute, value)
    assert assess_host_access_references(**fields).reason_code == reason


def test_missing_source_and_ee_attestation_rejected():
    fields = _evidence()
    fields['connection'].metadata_json['source_validation']['operation_authorized'] = True
    assert assess_host_access_references(**fields).reason_code == 'IMMUTABLE_SOURCE_NOT_QUALIFIED'
    fields = _evidence()
    fields['connection'].metadata_json['execution_environment_digest'] = 'latest'
    assert assess_host_access_references(**fields).reason_code == 'EXECUTION_ENVIRONMENT_REFERENCE_UNQUALIFIED'


@pytest.mark.parametrize('host_id', ['', '../unsafe', 'bad host', 'a' * 97])
def test_invalid_host_identity_rejected(host_id):
    assert _review(host_asset_id=host_id).reason_code == 'HOST_ASSET_IDENTITY_UNQUALIFIED'


@pytest.mark.parametrize(
    ('attribute', 'value', 'reason'),
    [
        ('lifecycle_status', 'retired', 'SECRET_IDENTITY_NOT_OBSERVED'),
    ],
)
def test_wrong_secret_identity_denied(attribute, value, reason):
    fields = _evidence()
    setattr(fields['secret_identity'], attribute, value)
    assert assess_host_access_references(**fields).reason_code == reason


@pytest.mark.parametrize(
    ('attribute', 'value'),
    [
        ('secret_identity_id', 'different-identity'),
        ('integration_instance_id', 0),
        ('provider_key', 'other'),
        ('representation_role', 'mirror'),
        ('observation_status', 'failed'),
        ('current_version', 0),
        ('current_version', True),
        ('path_sha256', 'not-a-digest'),
    ],
)
def test_unqualified_secret_representation_denied(attribute, value):
    fields = _evidence()
    setattr(fields['secret_representation'], attribute, value)
    assert (
        assess_host_access_references(**fields).reason_code
        == 'SECRET_PROVIDER_REFERENCE_UNQUALIFIED'
    )


@pytest.mark.parametrize('digest', [None, '', 'host-key', 'sha256:invalid'])
def test_missing_or_malformed_host_key_reference_denied(digest):
    assert _review(host_key_digest=digest).reason_code == 'HOST_KEY_REFERENCE_UNQUALIFIED'


def test_reference_drift_changes_hash_without_disclosing_material():
    fields = _evidence()
    first = assess_host_access_references(**fields).fingerprint
    fields['host_key_digest'] = 'sha256:' + 'f' * 64
    assert assess_host_access_references(**fields).fingerprint != first
    fields = _evidence()
    first = assess_host_access_references(**fields).fingerprint
    fields['secret_representation'].current_version = 3
    assert assess_host_access_references(**fields).fingerprint != first
    fields = _evidence()
    first = assess_host_access_references(**fields).fingerprint
    fields['connection'].metadata_json['execution_environment_digest'] = 'sha256:' + 'c' * 64
    assert assess_host_access_references(**fields).fingerprint != first
