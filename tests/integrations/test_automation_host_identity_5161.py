"""#5161: KAORI owns non-mutating existing-host asset and inventory identity."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure_automation.host_registry import (
    AutomationHostIntent,
    AutomationInventoryDenied,
    assign_host_to_ansible,
    preview_inventory_intent,
    require_ansible_connection,
    validate_host_intent,
)


def _connection(**changes):
    kwargs = {
        'id': 7,
        'environment': 'laboratory',
        'integration_type': 'configuration_automation',
        'provider_key': 'ansible',
        'lifecycle_status': 'active',
    }
    kwargs.update(changes)
    return SimpleNamespace(**kwargs)


def _assignment(asset='host-01', *, address='10.11.12.13', role='control_plane', **changes):
    host = SimpleNamespace(
        id=asset,
        name=asset,
        environment='laboratory',
        address=address,
        ssh_port=22,
        lifecycle_status='registered',
    )
    kwargs = {'integration_instance_id': 7, 'enabled': True, 'host': host, 'role': role}
    kwargs.update(changes)
    return SimpleNamespace(**kwargs)


@pytest.mark.parametrize(
    'values',
    [
        AutomationHostIntent('db01', 'production', '10.1.1.2'),
        AutomationHostIntent('Bad Upper', 'laboratory', '10.1.1.2'),
        AutomationHostIntent('node-01', 'laboratory', '127.0.0.1'),
        AutomationHostIntent('node-01', 'laboratory', '169.254.1.2'),
        AutomationHostIntent('node-01', 'laboratory', '192.0.2.5'),
        AutomationHostIntent('node-01', 'laboratory', '8.8.8.8'),
        AutomationHostIntent('node-01', 'laboratory', 'not-an-ip'),
        AutomationHostIntent('node-01', 'laboratory', '::1'),
        AutomationHostIntent('node-01', 'laboratory', '10.1.1.2', True),
        AutomationHostIntent('node-01', 'laboratory', '10.1.1.2', 65536),
    ],
)
def test_host_policy_denies_untrusted_addresses_and_production(values):
    with pytest.raises(AutomationInventoryDenied):
        validate_host_intent(values)


def test_private_host_identity_is_canonical_and_never_contains_secret_material():
    normalized = validate_host_intent(AutomationHostIntent('node-01', 'laboratory', '10.11.12.13'))
    assert normalized.address == '10.11.12.13'
    assert normalized.ssh_port == 22
    assert normalized.environment == 'laboratory'
    assert not hasattr(normalized, 'private_key')
    assert not hasattr(normalized, 'password')


@pytest.mark.parametrize(
    'changes',
    [
        {'environment': 'production'},
        {'integration_type': 'container_orchestrator'},
        {'provider_key': 'other'},
        {'lifecycle_status': 'retired'},
    ],
)
def test_wrong_ansible_source_scope_cannot_own_host_inventory(changes):
    with pytest.raises(AutomationInventoryDenied):
        require_ansible_connection(_connection(**changes), environment='laboratory')


def test_exact_fingerprint_changes_with_host_role_and_ip_and_never_grants_ssh():
    original = preview_inventory_intent(_connection(), [_assignment(), _assignment('host-02', role='worker')])
    assert original.state == 'requires_trust_admission'
    assert original.host_count == 2
    assert len(original.inventory_fingerprint or '') == 64
    assert not original.execution_authorized
    assert '10.11.12.13' not in str(original.presentation())
    changed_address = preview_inventory_intent(
        _connection(), [_assignment(address='10.11.12.15'), _assignment('host-02', role='worker')]
    )
    changed_role = preview_inventory_intent(
        _connection(), [_assignment(role='worker'), _assignment('host-02', role='worker')]
    )
    assert original.inventory_fingerprint != changed_address.inventory_fingerprint
    assert original.inventory_fingerprint != changed_role.inventory_fingerprint


def test_malformed_duplicate_or_cross_connection_assignment_fails_closed():
    assert preview_inventory_intent(_connection(), []).state == 'blocked'
    assert preview_inventory_intent(_connection(), [_assignment(), _assignment()]).state == 'blocked'
    assert preview_inventory_intent(_connection(), [_assignment(integration_instance_id=8)]).state == 'blocked'
    assert preview_inventory_intent(_connection(), [_assignment(enabled=False)]).state == 'blocked'
    assert preview_inventory_intent(_connection(), [_assignment(role='etcd')]).state == 'blocked'
    assert preview_inventory_intent(_connection(), [_assignment(address='169.254.1.2')]).state == 'blocked'


def test_assignment_rejects_mismatched_connection_without_writing():
    with pytest.raises(AutomationInventoryDenied):
        assign_host_to_ansible(
            _connection(environment='production'),
            _assignment().host,
            role='worker',
        )
