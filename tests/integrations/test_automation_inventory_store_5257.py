"""Exact immutable provider inventory readback regression (#5257)."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.infrastructure_automation.kubernetes.inventory_document import build_inventory_document, digest
from app.infrastructure_automation.kubernetes.inventory_kv import (
    InventoryStoreReference,
    stored_document,
    verify_or_publish,
)
from app.infrastructure_automation.kubernetes.source_policy import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError


def _fixture():
    inventory = {'schema': 'fixture', 'connection_id': 3, 'execution_authorized': False}
    provisional = InventoryStoreReference(7, 'openbao', 'fixture', 'fixture-kv', 3, '')
    expected = stored_document(provisional, inventory)
    reference = InventoryStoreReference(7, 'openbao', 'fixture', 'fixture-kv', 3, digest(expected))
    response = {'data': {'data': {'document': expected}, 'metadata': {'version': 1, 'destroyed': False, 'deletion_time': ''}}}
    return inventory, reference, response


def test_publish_uses_cas_zero_and_exact_readback():
    inventory, reference, response = _fixture()
    transport = Mock()
    transport._request.side_effect = [(404, {}), (200, {'data': {'version': 1}}), (200, response)]
    verify_or_publish(transport, reference, inventory, token='fixture', publish=True)
    assert transport._request.call_count == 3
    assert transport._request.call_args_list[1].kwargs['payload']['options'] == {'cas': 0}


def test_existing_exact_document_is_not_overwritten():
    inventory, reference, response = _fixture()
    transport = Mock()
    transport._request.return_value = (200, response)
    verify_or_publish(transport, reference, inventory, token='fixture', publish=True)
    assert transport._request.call_count == 1


@pytest.mark.parametrize('status', [403, 404, 503])
def test_read_only_denies_missing_or_unavailable(status):
    inventory, reference, _response = _fixture()
    transport = Mock()
    transport._request.return_value = (status, {})
    with pytest.raises(SecretProviderError):
        verify_or_publish(transport, reference, inventory, token='fixture', publish=False)
    assert transport._request.call_count == 1


@pytest.mark.parametrize('field,value', [('version', 2), ('version', True), ('destroyed', True), ('deletion_time', 'deleted')])
def test_version_drift_or_deleted_document_never_overwritten(field, value):
    inventory, reference, response = _fixture()
    response['data']['metadata'][field] = value
    transport = Mock()
    transport._request.return_value = (200, response)
    with pytest.raises(SecretProviderError):
        verify_or_publish(transport, reference, inventory, token='fixture', publish=True)
    assert transport._request.call_count == 1


def _source_only():
    return SimpleNamespace(
        id=11,
        integration_type='configuration_automation',
        provider_key='ansible',
        lifecycle_status='active',
        readiness_status='validation_required',
        environment='development',
        enabled=False,
        metadata_json={
            'source_repository': REPOSITORY,
            'source_sha': SOURCE_CANDIDATE_SHA,
            'profile_key': PROFILE_KEY,
            'ansible_core_version': ANSIBLE_CORE_VERSION,
            'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
            'kubespray_release': KUBESPRAY_RELEASE,
            'execution_enabled': False,
            'mutation_authorized': False,
            'source_validation': {
                'status': 'source_checked',
                'repository': REPOSITORY,
                'revision': SOURCE_CANDIDATE_SHA,
                'profile_key': PROFILE_KEY,
                'checked_files': 5,
                'operation_authorized': False,
            },
        },
    )


def _assignments():
    return [
        SimpleNamespace(
            integration_instance_id=11,
            host_id=f'host-{i}',
            enabled=True,
            role='control_plane' if i == 1 else 'worker',
            host=SimpleNamespace(
                id=f'host-{i}',
                name=f'host-{i}',
                address=f'10.20.30.{i}',
                ssh_port=22,
                environment='development',
                lifecycle_status='registered',
            ),
        )
        for i in range(1, 4)
    ]


def _document(connection, *, preparation=False):
    return build_inventory_document(
        connection,
        _assignments(),
        pod_cidr='10.244.0.0/16',
        service_cidr='10.96.0.0/16',
        allow_source_only_preparation=preparation,
    )


def test_local_preparation_works_before_runtime_admission_without_changing_identity():
    connection = _source_only()
    with pytest.raises(ValueError):
        _document(connection)
    prepared = _document(connection, preparation=True)
    assert prepared['execution_authorized'] is False
    assert prepared['connection_id'] == connection.id
    assert connection.enabled is False
    connection.enabled = True
    assert _document(connection) == prepared


@pytest.mark.parametrize(
    'changes',
    [
        {'lifecycle_status': 'retired'},
        {'readiness_status': 'ready'},
        {'environment': 'production'},
        {'provider_key': 'other'},
        {'enabled': None},
    ],
)
def test_local_preparation_does_not_bypass_connection_scope(changes):
    connection = _source_only()
    for key, value in changes.items():
        setattr(connection, key, value)
    with pytest.raises(ValueError):
        _document(connection, preparation=True)


@pytest.mark.parametrize('field', ['execution_enabled', 'mutation_authorized', 'source_validation'])
def test_local_preparation_requires_explicit_negative_authority_and_checked_source(field):
    connection = _source_only()
    del connection.metadata_json[field]
    with pytest.raises(ValueError):
        _document(connection, preparation=True)
