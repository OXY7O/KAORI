"""Exact immutable provider inventory readback regression (#5257)."""

from unittest.mock import Mock

import pytest

from app.infrastructure_automation.kubernetes.inventory_document import digest
from app.infrastructure_automation.kubernetes.inventory_kv import (
    InventoryStoreReference,
    stored_document,
    verify_or_publish,
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
