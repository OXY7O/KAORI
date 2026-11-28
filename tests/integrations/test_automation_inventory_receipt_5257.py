"""#5257: Provider KV v2 inventory readback is historical, scoped evidence only."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from app.infrastructure_automation.kubernetes.inventory_document import digest
from app.infrastructure_automation.kubernetes.inventory_kv import InventoryStoreReference, stored_document
from app.infrastructure_automation.kubernetes.inventory_receipt import review_inventory_receipt
from app.infrastructure_automation.kubernetes.source_policy import ANSIBLE_CORE_VERSION

NOW = datetime(2026, 11, 28, 2, 0, tzinfo=UTC)
ENDPOINT = 'https://secret-store:8200'
CLUSTER = '123e4567-e89b-42d3-a456-426614174000'


def _evidence(provider_key: str = 'openbao', *, parser: str = 'verified'):
    inventory = {
        'schema': 'kaori.kubespray.inventory_config.v1',
        'connection_id': 11,
        'source_repository': 'OXY7O/kaori-operations',
        'source_sha': 'a' * 40,
        'host_registry_fingerprint': 'b' * 64,
        'config': {'pod_cidr': '10.244.0.0/16', 'service_cidr': '10.96.0.0/16'},
        'execution_authorized': False,
    }
    reference = InventoryStoreReference(22, provider_key, CLUSTER, 'approved-kv', 11, '')
    receipt = {
        'schema_version': 1,
        'provider_id': 22,
        'provider_key': provider_key,
        'provider_origin_sha256': sha256(ENDPOINT.encode()).hexdigest(),
        'cluster_id': CLUSTER,
        'mount': 'approved-kv',
        'version': 1,
        'source_repository': inventory['source_repository'],
        'source_sha': inventory['source_sha'],
        'host_registry_fingerprint': inventory['host_registry_fingerprint'],
        'pod_cidr': inventory['config']['pod_cidr'],
        'service_cidr': inventory['config']['service_cidr'],
        'fingerprint': digest(stored_document(reference, inventory)),
        'observed_at': (NOW - timedelta(minutes=5)).isoformat(),
        'execution_authorized': False,
        'ansible_inventory_parser': parser,
        'ansible_core_version': ANSIBLE_CORE_VERSION if parser == 'verified' else None,
    }
    return receipt, inventory


def _review(receipt, inventory, **overrides):
    values = {
        'connection_id': 11, 'provider_id': 22, 'provider_key': 'openbao',
        'endpoint': ENDPOINT, 'now': NOW,
    }
    values.update(overrides)
    return review_inventory_receipt(receipt, inventory=inventory, **values)


def test_exact_observation_is_historical_not_run_or_credential_authority():
    receipt, inventory = _evidence()
    result = _review(receipt, inventory)
    assert result.state == 'historical_aligned'
    assert result.parser_verified is True
    assert result.fingerprint == receipt['fingerprint']
    assert result.execution_authorized is False
    assert set(result.presentation()) == {
        'state', 'description', 'provider_label', 'fingerprint', 'observed_at',
        'parser_verified', 'execution_authorized',
    }
    assert ENDPOINT not in str(result.presentation())
    assert receipt['mount'] not in str(result.presentation())
    assert CLUSTER not in str(result.presentation())


def test_parser_pending_cannot_be_presented_as_parser_verified():
    receipt, inventory = _evidence(parser='not_checked')
    result = _review(receipt, inventory)
    assert result.state == 'parser_unchecked'
    assert result.parser_verified is False
    assert result.execution_authorized is False


def test_no_receipt_and_legacy_receipt_are_not_implicitly_current():
    receipt, inventory = _evidence()
    assert _review(None, inventory).state == 'not_recorded'
    del receipt['schema_version']
    assert _review(receipt, inventory).state == 'unqualified'


@pytest.mark.parametrize('field,value', [
    ('schema_version', True), ('schema_version', 2), ('version', True),
    ('version', 2), ('execution_authorized', True), ('provider_id', True),
    ('provider_key', 'vault'), ('ansible_inventory_parser', 'assumed'),
    ('fingerprint', 'not-a-digest'), ('observed_at', 'invalid'),
    ('observed_at', '2026-11-28T04:00:00+00:00'),
    ('observed_at', '2026-11-28T00:00:00'),
])
def test_invalid_receipt_never_yields_historical_alignment(field, value):
    receipt, inventory = _evidence()
    receipt[field] = value
    assert _review(receipt, inventory).state != 'historical_aligned'


@pytest.mark.parametrize('field,value', [
    ('provider_id', 99), ('provider_key', 'vault'),
    ('endpoint', 'https://different-provider:8200'),
])
def test_provider_substitution_is_blocked(field, value):
    receipt, inventory = _evidence()
    assert _review(receipt, inventory, **{field: value}).state == 'provider_changed'


@pytest.mark.parametrize('field,value', [
    ('source_sha', 'c' * 40), ('host_registry_fingerprint', 'd' * 64),
    ('source_repository', 'OXY7O/another-repo'),
])
def test_source_or_host_drift_is_blocked(field, value):
    receipt, inventory = _evidence()
    modified = deepcopy(inventory)
    modified[field] = value
    assert _review(receipt, modified).state == 'source_changed'


def test_network_host_and_document_drift_block_exact_fingerprint():
    receipt, inventory = _evidence()
    assert _review(receipt, None).state == 'source_changed'
    modified = deepcopy(inventory)
    modified['config']['pod_cidr'] = '10.245.0.0/16'
    assert _review(receipt, modified).state == 'source_changed'
    modified = deepcopy(inventory)
    modified['hosts'] = ['unknown-host']
    assert _review(receipt, modified).state == 'source_changed'
    assert _review(receipt, inventory, connection_id=12).state == 'source_changed'


def test_vault_is_supported_without_cross_provider_fallback():
    receipt, inventory = _evidence('vault')
    assert _review(receipt, inventory, provider_key='vault').state == 'historical_aligned'
    assert _review(receipt, inventory, provider_key='openbao').state == 'provider_changed'


def test_native_parser_version_drift_requires_fresh_readback():
    receipt, inventory = _evidence()
    receipt['ansible_core_version'] = '2.19.0'
    assert _review(receipt, inventory).state == 'unqualified'


def test_malformed_network_config_fails_closed_without_type_errors():
    receipt, inventory = _evidence()
    inventory['config'] = None
    assert _review(receipt, inventory).state == 'source_changed'
