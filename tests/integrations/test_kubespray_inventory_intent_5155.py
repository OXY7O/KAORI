"""Issue #5155: host inventory fingerprint is neither execution inventory nor approval."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.infrastructure_automation.inventory_intent import (
    InventoryHostIntent,
    build_kubespray_inventory_review,
)


def _hosts() -> tuple[InventoryHostIntent, ...]:
    return (
        InventoryHostIntent('cp-01', '10.25.1.11', 22, 'control_plane', 'ref-cp', 'hk-cp'),
        InventoryHostIntent('worker-01', '10.25.1.12', 22, 'worker', 'ref-w1', 'hk-w1'),
        InventoryHostIntent('worker-02', '10.25.1.13', 2222, 'worker', 'ref-w2', 'hk-w2'),
    )


def _review(**changes):
    fields = {
        'connection_id': 77,
        'environment': 'laboratory',
        'source_sha': 'a' * 40,
        'execution_environment_digest': 'sha256:' + 'b' * 64,
        'hosts': _hosts(),
    }
    fields.update(changes)
    return build_kubespray_inventory_review(**fields)


def test_valid_intent_produces_deterministic_redacted_review_only_fingerprint():
    result = _review()
    reordered = _review(hosts=tuple(reversed(_hosts())))
    assert result.status == 'review_only'
    assert result.reason_code == 'INDEPENDENT_ADMISSION_REQUIRED'
    assert result.fingerprint == reordered.fingerprint
    assert result.execution_authorized is False
    assert result.committed_summary()['execution_authorized'] is False
    assert result.committed_summary()['host_count'] == 3
    for sensitive in ('10.25.', 'ref-cp', 'hk-cp', 'cp-01'):
        assert sensitive not in str(result.committed_summary())


@pytest.mark.parametrize(
    ('changes', 'reason'),
    [
        ({'connection_id': 0}, 'CONNECTION_ID_UNQUALIFIED'),
        ({'connection_id': True}, 'CONNECTION_ID_UNQUALIFIED'),
        ({'environment': 'production'}, 'NON_PRODUCTION_ONLY'),
        ({'source_sha': 'latest'}, 'SOURCE_REVISION_UNQUALIFIED'),
        ({'execution_environment_digest': 'sha256:mutable'}, 'EXECUTION_ENVIRONMENT_UNQUALIFIED'),
        ({'hosts': ()}, 'PILOT_TOPOLOGY_UNQUALIFIED'),
        ({'hosts': list(_hosts())}, 'PILOT_TOPOLOGY_UNQUALIFIED'),
        ({'hosts': ('arbitrary-host-json',) * 3}, 'HOST_RECORD_UNQUALIFIED'),
    ],
)
def test_invalid_scope_and_source_fail_closed(changes, reason):
    result = _review(**changes)
    assert result.status == 'blocked'
    assert result.reason_code == reason
    assert result.fingerprint is None
    assert not result.execution_authorized


@pytest.mark.parametrize(
    ('index', 'changed', 'reason'),
    [
        (0, {'asset_id': '../inventory'}, 'HOST_IDENTITY_UNQUALIFIED'),
        (0, {'address': '8.8.8.8'}, 'HOST_ENDPOINT_UNQUALIFIED'),
        (0, {'address': '127.0.0.1'}, 'HOST_ENDPOINT_UNQUALIFIED'),
        (0, {'address': '10.25.1.11 '}, 'HOST_ENDPOINT_UNQUALIFIED'),
        (0, {'ssh_port': True}, 'HOST_ENDPOINT_UNQUALIFIED'),
        (0, {'ssh_port': 65536}, 'HOST_ENDPOINT_UNQUALIFIED'),
        (0, {'role': 'etcd'}, 'HOST_ROLE_UNQUALIFIED'),
        (0, {'credential_reference': ''}, 'HOST_ACCESS_REFERENCE_UNQUALIFIED'),
        (0, {'ssh_host_key_reference': 'invalid-reference\n'}, 'HOST_ACCESS_REFERENCE_UNQUALIFIED'),
        (1, {'asset_id': 'cp-01'}, 'DUPLICATE_HOST_IDENTITY'),
        (1, {'address': '10.25.1.11'}, 'DUPLICATE_HOST_IDENTITY'),
        (1, {'role': 'control_plane'}, 'PILOT_TOPOLOGY_UNQUALIFIED'),
    ],
)
def test_invalid_asset_endpoint_role_or_access_reference_blocks(index, changed, reason):
    hosts = list(_hosts())
    hosts[index] = replace(hosts[index], **changed)
    result = _review(hosts=tuple(hosts))
    assert result.status == 'blocked'
    assert result.reason_code == reason


def test_fingerprint_changes_on_host_ip_access_source_or_ee_changes():
    before = _review().fingerprint
    assert before is not None
    hosts = list(_hosts())
    for changed in (
        {'address': '10.25.1.99'},
        {'ssh_port': 2222},
        {'credential_reference': 'ref-new'},
        {'ssh_host_key_reference': 'hk-new'},
    ):
        altered = hosts.copy()
        altered[0] = replace(altered[0], **changed)
        assert _review(hosts=tuple(altered)).fingerprint != before
    assert _review(source_sha='c' * 40).fingerprint != before
    assert _review(execution_environment_digest='sha256:' + 'd' * 64).fingerprint != before
    assert _review(connection_id=78).fingerprint != before
