"""Negative admission contracts for source-owned Kubespray host observations (#4799)."""

from app.integrations.orchestration.configuration_automation.providers.ansible.preflight import (
    _valid_pilot_hosts,
    _valid_pilot_network,
)


def _hosts():
    return [
        {
            'asset_id': f'asset-{i}',
            'role': 'control_plane' if i == 0 else 'worker',
            'asset_identity_verified': True,
            'os_distribution': 'Ubuntu',
            'os_release': '24.04',
            'cpu_count': 2,
            'memory_mib': 4096,
            'disk_gib': 40,
        }
        for i in range(3)
    ]


def test_remote_host_identity_rejects_ambiguous_asset_keys():
    for identity in (' asset-0', 'asset-0 ', ' ', 'x' * 97):
        hosts = _hosts()
        hosts[0]['asset_id'] = identity
        assert _valid_pilot_hosts({'hosts': hosts}) is False


def test_remote_host_identity_accepts_distinct_exact_asset_keys():
    assert _valid_pilot_hosts({'hosts': _hosts()}) is True


def test_network_observation_rejects_default_route_as_host_network():
    facts = {
        'pod_cidr': '10.233.0.0/16',
        'service_cidr': '10.96.0.0/16',
        'host_network_cidrs': ['0.0.0.0/0'],
    }
    assert _valid_pilot_network(facts) is False


def test_network_observation_accepts_disjoint_concrete_network():
    facts = {
        'pod_cidr': '10.233.0.0/16',
        'service_cidr': '10.96.0.0/16',
        'host_network_cidrs': ['192.168.80.0/24'],
    }
    assert _valid_pilot_network(facts) is True
