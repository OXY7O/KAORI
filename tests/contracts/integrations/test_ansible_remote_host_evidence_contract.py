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


def test_network_observation_rejects_non_routable_host_ranges():
    base = {
        'pod_cidr': '10.233.0.0/16',
        'service_cidr': '10.96.0.0/16',
    }
    for host_cidr in ('0.0.0.0/0', '127.0.0.1/32', '169.254.1.0/24', '224.0.0.0/4'):
        assert _valid_pilot_network({**base, 'host_network_cidrs': [host_cidr]}) is False


def test_network_observation_allows_public_unicast_host_network_without_overlap():
    facts = {
        'pod_cidr': '10.233.0.0/16',
        'service_cidr': '10.96.0.0/16',
        'host_network_cidrs': ['198.51.100.0/24'],
    }
    assert _valid_pilot_network(facts) is True


def test_remote_host_identity_rejects_invisible_or_control_unicode():
    # Unicode category C covers control, format, surrogate, private-use and
    # unassigned characters, including bidi override and zero-width joiners.
    for identity in ('asset-0\\n', 'asset-0\\t', 'asset-\\u200b0', 'asset-\\u202e0', 'asset-\\ue0000'):
        hosts = _hosts()
        hosts[0]['asset_id'] = identity
        assert _valid_pilot_hosts({'hosts': hosts}) is False


def test_remote_host_identity_accepts_printable_unicode_identifier():
    hosts = _hosts()
    hosts[0]['asset_id'] = 'asset-café'
    assert _valid_pilot_hosts({'hosts': hosts}) is True
