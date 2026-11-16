from __future__ import annotations

from copy import deepcopy

import pytest

from app.infrastructure_automation.kubernetes.kubespray_preflight import (
    KUBESPRAY_COMMIT,
    StaticKubesprayPlan,
    assess_static_kubespray_pilot,
)


def _pilot() -> dict:
    return {
        'management': 'self_managed',
        'environment': 'uat',
        'kubespray_release': 'v2.32.0',
        'kubespray_commit': KUBESPRAY_COMMIT,
        'kubernetes_minor': '1.36',
        'pod_cidr': '10.244.0.0/16',
        'service_cidr': '10.96.0.0/12',
        # RFC 5737 documentation addresses; no real targets or private inventory.
        'nodes': [
            {
                'asset_id': f'example-{i}',
                'role': 'control_plane' if i == 1 else 'worker',
                'os_distribution': 'OracleLinux',
                'os_version': '9',
                'cpu_count': 4,
                'memory_mib': 8192,
                'disk_gib': 100,
                'address': f'192.0.2.{i}',
            }
            for i in range(1, 4)
        ],
    }


def test_valid_static_pilot_never_authorizes_mutation() -> None:
    result = assess_static_kubespray_pilot(_pilot())
    assert isinstance(result, StaticKubesprayPlan)
    assert result.status == 'requires_provider_evidence'
    assert result.inventory_fingerprint
    assert not result.findings
    assert result.mutation_authorized is False
    assert 'human_risk_approval_and_maintenance_window' in result.required_evidence


@pytest.mark.parametrize(
    ('field', 'value', 'finding'),
    [
        ('management', 'aws_eks', 'UNSUPPORTED_MANAGED_KUBERNETES'),
        ('environment', 'production', 'NON_PRODUCTION_ONLY'),
        ('kubespray_release', 'latest', 'KUBESPRAY_RELEASE_MISMATCH'),
        ('kubespray_commit', 'main', 'KUBESPRAY_SHA_MISMATCH'),
        ('kubernetes_minor', '1.37', 'KUBERNETES_MINOR_UNQUALIFIED'),
        ('pod_cidr', '10.96.0.0/12', 'POD_SERVICE_NETWORK_OVERLAP'),
        ('pod_cidr', '0.0.0.0/0', 'POD_CIDR_MUST_BE_PRIVATE_IPV4'),
        ('service_cidr', 'not-a-network', 'SERVICE_CIDR_INVALID'),
    ],
)
def test_rejects_unqualified_cluster_spec(field: str, value: object, finding: str) -> None:
    spec = _pilot()
    spec[field] = value
    plan = assess_static_kubespray_pilot(spec)
    assert plan.status == 'blocked'
    assert finding in plan.findings
    assert plan.mutation_authorized is False


def test_rejects_extra_secret_field_without_reflecting_value() -> None:
    spec = _pilot()
    spec['ssh_private_key'] = 'should-not-enter-public-state'
    plan = assess_static_kubespray_pilot(spec)
    assert 'UNRECOGNIZED_OR_SENSITIVE_INPUT' in plan.findings
    assert 'should-not-enter-public-state' not in repr(plan)
    assert plan.inventory_fingerprint is None


def test_rejects_duplicate_node_asset_and_address() -> None:
    spec = _pilot()
    spec['nodes'][1] = deepcopy(spec['nodes'][0])
    plan = assess_static_kubespray_pilot(spec)
    assert 'DUPLICATE_NODE_ASSET' in plan.findings
    assert 'DUPLICATE_NODE_ADDRESS' in plan.findings


def test_rejects_worker_address_in_pod_network() -> None:
    spec = _pilot()
    spec['nodes'][2]['address'] = '10.244.0.12'
    plan = assess_static_kubespray_pilot(spec)
    assert 'NODE_ADDRESS_OVERLAPS_CLUSTER_CIDR' in plan.findings


def test_rejects_non_ha_pilot_role_mismatch() -> None:
    spec = _pilot()
    spec['nodes'][1]['role'] = 'control_plane'
    plan = assess_static_kubespray_pilot(spec)
    assert 'PILOT_REQUIRES_ONE_CONTROL_PLANE_TWO_WORKERS' in plan.findings


def test_rejects_unqualified_target_os_and_resources() -> None:
    spec = _pilot()
    spec['nodes'][0]['os_distribution'] = 'Unknown'
    spec['nodes'][0]['cpu_count'] = 0
    plan = assess_static_kubespray_pilot(spec)
    assert 'NODE_OS_UNQUALIFIED' in plan.findings
    assert 'NODE_RESOURCES_BELOW_PILOT_MINIMUM' in plan.findings


def test_fingerprint_is_deterministic_and_never_full_inventory() -> None:
    one = assess_static_kubespray_pilot(_pilot())
    two = assess_static_kubespray_pilot(_pilot())
    assert one.inventory_fingerprint == two.inventory_fingerprint
    assert '192.0.2.' not in repr(one)


@pytest.mark.parametrize(
    ('field', 'invalid'),
    [
        ('environment', ['uat']),
        ('pod_cidr', {'cidr': '10.244.0.0/16'}),
    ],
)
def test_invalid_container_values_fail_closed(field: str, invalid: object) -> None:
    spec = _pilot()
    spec[field] = invalid
    plan = assess_static_kubespray_pilot(spec)
    assert plan.status == 'blocked'
    assert plan.mutation_authorized is False


def test_unhashable_node_fields_fail_closed_without_provider_call() -> None:
    spec = _pilot()
    spec['nodes'][0]['role'] = ['control_plane']
    spec['nodes'][0]['os_distribution'] = ['OracleLinux']
    plan = assess_static_kubespray_pilot(spec)
    assert plan.status == 'blocked'
    assert 'NODE_ROLE_UNSUPPORTED' in plan.findings
    assert 'NODE_OS_UNQUALIFIED' in plan.findings


@pytest.mark.parametrize('invalid', [None, [], 'not-a-spec', 12, {None: 'value'}])
def test_malformed_root_spec_is_blocked_without_exception(invalid: object) -> None:
    plan = assess_static_kubespray_pilot(invalid)  # type: ignore[arg-type]
    assert plan.status == 'blocked'
    assert plan.findings == ('SPEC_SCHEMA_INVALID',)
    assert plan.inventory_fingerprint is None
    assert plan.mutation_authorized is False


def test_blank_asset_identity_cannot_generate_review_fingerprint() -> None:
    spec = _pilot()
    spec['nodes'][0]['asset_id'] = '   '
    plan = assess_static_kubespray_pilot(spec)
    assert plan.status == 'blocked'
    assert 'NODE_ASSET_ID_INVALID' in plan.findings
    assert plan.inventory_fingerprint is None
