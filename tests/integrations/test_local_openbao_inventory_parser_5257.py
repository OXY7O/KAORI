"""Provider overview and offline inventory compiler regression."""

from types import SimpleNamespace

import pytest

from app.infrastructure_automation.kubernetes.inventory_parser import compile_inventory
from app.integrations.secrets_management.secrets_pki.providers.openbao import presentation


def test_inventory_compiler_fixed_groups_no_credentials():
    document = {
        'schema': 'kaori.kubespray.inventory_config.v1',
        'execution_authorized': False,
        'hosts': [
            {'name': name, 'role': role, 'address': f'10.0.0.{i}', 'ssh_port': 22}
            for i, (name, role) in enumerate(
                [('cp', 'control_plane'), ('worker-a', 'worker'), ('worker-b', 'worker')], 1
            )
        ],
        'config': {'pod_cidr': '10.244.0.0/16', 'service_cidr': '10.96.0.0/16'},
    }
    result = compile_inventory(document)['all']
    assert set(result['children']['etcd']['hosts']) == {'cp'}
    assert set(result['children']['kube_node']['hosts']) == {'worker-a', 'worker-b'}
    assert set(result['hosts']['cp']) == {'ansible_host', 'ansible_port', 'ip', 'access_ip'}
    assert result['vars']['kube_pods_subnet'] == '10.244.0.0/16'
    document['execution_authorized'] = True
    with pytest.raises(ValueError):
        compile_inventory(document)


def test_openbao_runtime_never_uses_vault_observation(monkeypatch):
    monkeypatch.setattr(presentation, 'local_provider_enabled', lambda: True)
    identity = SimpleNamespace(
        id=91, enabled=True, lifecycle_status='active', health_status='connected',
        readiness_status='degraded', last_error=None, bindings=[],
    )
    row = SimpleNamespace(id=3, name='fixture', ownership='internal', integration_instance=identity, last_validated_at=None)
    foreign = SimpleNamespace(integration_instance_id=91, provider_key='vault', adapter_key='vault_http_v1')
    result = presentation._runtime_row(row, foreign)
    assert result['health_status'] == 'not_observed'
    assert result['detail_key'] == 'secrets_pki:91'
    assert result['instance_id'] == 'openbao:3'
    assert result['readiness'] == 'degraded'
