"""Metadata-only OpenBao collection through the canonical commit boundary."""

from unittest.mock import Mock

import pytest

from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import collect_kv2_metadata_with_token
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.openbao import inventory
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import LocalOpenBaoInventoryScope


def test_openbao_metadata_traversal_does_not_access_data_or_login():
    transport = Mock()
    transport._request.side_effect = [
        (200, {'data': {'keys': ['ssh']}}),
        (200, {'data': {'current_version': 1, 'oldest_version': 1, 'max_versions': 10,
                         'cas_required': True, 'versions': {'1': {'created_time': '2026-11-27T00:00:00Z',
                         'deletion_time': '', 'destroyed': False}}}}),
    ]
    evidence = collect_kv2_metadata_with_token(transport, mount='fixture', token='fixture-token')
    assert len(evidence.records) == 1
    assert evidence.records[0].current_version == 1
    assert [call.args[0] for call in transport._request.call_args_list] == [
        '/v1/fixture/metadata', '/v1/fixture/metadata/ssh'
    ]
    transport.login.assert_not_called()


def test_mount_type_drift_denies_collection():
    transport = Mock()
    transport._request.return_value = (200, {'data': {'fixture/': {'type': 'kv', 'options': {'version': '1'}}}})
    scope = LocalOpenBaoInventoryScope(1, 'fixture', 'https://bao.example.invalid', 'fixture', 'external')
    with pytest.raises(SecretProviderError):
        inventory._require_mount(transport, scope, 'fixture-token')
