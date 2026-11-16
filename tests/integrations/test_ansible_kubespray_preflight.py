"""Issue #4800: Kubespray preflight refuses to confuse Git source with execution.

No provider, SSH, Runner, Celery or live Kubernetes calls occur in these tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.integrations.orchestration.configuration_automation.providers.ansible.preflight import (
    build_kubespray_preflight,
)
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)

_NOW = datetime(2026, 11, 16, 2, 0, tzinfo=UTC)


def _connection(*, source_checked: bool = True, environment: str = 'laboratory'):
    return SimpleNamespace(
        id=77,
        environment=environment,
        metadata_json={
            'profile_key': PROFILE_KEY,
            'source_repository': REPOSITORY,
            'source_sha': SOURCE_CANDIDATE_SHA,
            'ansible_core_version': ANSIBLE_CORE_VERSION,
            'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
            'kubespray_release': KUBESPRAY_RELEASE,
            'execution_environment_digest': None,
            'execution_enabled': False,
            'mutation_authorized': False,
            'source_validation': {
                'status': 'source_checked' if source_checked else 'blocked',
                'repository': REPOSITORY,
                'revision': SOURCE_CANDIDATE_SHA,
                'profile_key': PROFILE_KEY,
                'checked_files': 5,
                'operation_authorized': False,
            },
        },
    )


def _job(**changes):
    fields = {
        'integration_instance_id': 77,
        'integration_type': 'configuration_automation',
        'job_type': 'infrastructure_automation',
        'operation': 'automation_kubespray_host_preflight',
        'result_type': 'automation_kubespray_host_preflight_v1',
        'status': 'succeeded',
        'completed_at': _NOW - timedelta(minutes=3),
        'public_id': 'canonical-job-42',
        'result_summary_json': {
            'repository': REPOSITORY,
            'source_sha': SOURCE_CANDIDATE_SHA,
            'scope': 'self_managed_existing_linux_hosts',
            'target_class': 'self_managed_existing_linux_hosts',
            'attestation': 'verified_by_automation_worker',
            'image_provenance_verified': True,
            'host_keys_verified': True,
            'credential_reference_verified': True,
            'privileged_identity_verified': True,
            'os_support_verified': True,
            'capacity_verified': True,
            'network_verified': True,
            'dns_verified': True,
            'time_sync_verified': True,
            'etcd_quorum_verified': True,
            'control_plane_endpoint_verified': True,
            'cri_cni_compatibility_verified': True,
            'worker_execution_admitted': True,
            'exact_inventory_verified': True,
            'plan_fingerprint_verified': True,
            'maker_checker_approval_verified': True,
            'maintenance_window_verified': True,
            'high_availability': False,
            'upstream_kubespray_release': 'v2.32.0',
            'kubernetes_minor': '1.36',
            'service_cidr': '10.233.0.0/18',
            'pod_cidr': '10.233.64.0/18',
            'host_network_cidrs': ['172.16.10.0/24'],
            'hosts': [
                {
                    'asset_id': 'host-cp-01',
                    'asset_identity_verified': True,
                    'role': 'control_plane',
                    'os_distribution': 'OracleLinux',
                    'os_release': '9',
                    'cpu_count': 4,
                    'memory_mib': 8192,
                    'disk_gib': 100,
                },
                {
                    'asset_id': 'host-worker-01',
                    'asset_identity_verified': True,
                    'role': 'worker',
                    'os_distribution': 'Ubuntu',
                    'os_release': '24.04',
                    'cpu_count': 4,
                    'memory_mib': 8192,
                    'disk_gib': 100,
                },
                {
                    'asset_id': 'host-worker-02',
                    'asset_identity_verified': True,
                    'role': 'worker',
                    'os_distribution': 'Ubuntu',
                    'os_release': '24.04',
                    'cpu_count': 4,
                    'memory_mib': 8192,
                    'disk_gib': 100,
                },
            ],
        },
    }
    fields.update(changes)
    return SimpleNamespace(**fields)


def test_source_only_registration_is_not_an_executable_plan() -> None:
    report = build_kubespray_preflight(_connection(), now=_NOW)
    assert report.state == 'blocked'
    assert report.required_gates == 10
    assert report.verified_gates == 1
    assert report.facts_job_public_id is None
    assert report.gates[0].state == 'ready'
    assert all(gate.state == 'blocked' for gate in report.gates[1:])
    assert report.presentation()['gates'][1]['key'] == 'target_classification'


def test_verified_worker_evidence_is_still_only_ready_for_review() -> None:
    report = build_kubespray_preflight(_connection(), jobs=[_job()], now=_NOW)
    assert report.state == 'ready_for_review'
    assert report.verified_gates == 8
    assert report.required_gates == 10
    assert {gate.key for gate in report.gates if gate.state == 'blocked'} == {'execution_scope', 'approval'}
    assert report.facts_job_public_id == 'canonical-job-42'
    assert 'mutation_authorized' not in report.presentation()
    assert report.source_revision == SOURCE_CANDIDATE_SHA


@pytest.mark.parametrize(
    'change',
    [
        {'integration_instance_id': 999},
        {'integration_type': 'artifact_registry'},
        {'job_type': 'inventory'},
        {'operation': 'automation_localhost_host_facts'},
        {'result_type': 'automation_read_only_host_facts'},
        {'status': 'failed'},
        {'completed_at': _NOW - timedelta(minutes=16)},
        {'completed_at': _NOW + timedelta(minutes=1)},
        {'completed_at': datetime(2026, 11, 16, 2, 0)},
        {'completed_at': None},
        {'result_summary_json': {'repository': REPOSITORY}},
        {'result_summary_json': {'source_sha': SOURCE_CANDIDATE_SHA}},
    ],
)
def test_unrelated_stale_or_unattested_jobs_cannot_qualify_a_plan(change) -> None:
    report = build_kubespray_preflight(_connection(), jobs=[_job(**change)], now=_NOW)
    assert report.state == 'blocked'
    assert report.verified_gates == 1
    assert report.facts_job_public_id is None


@pytest.mark.parametrize(
    ('changed', 'gate_key'),
    [
        ({'image_provenance_verified': False}, 'source_and_ee_admission'),
        ({'host_keys_verified': False}, 'host_identity'),
        ({'credential_reference_verified': False}, 'host_identity'),
        ({'os_support_verified': False}, 'host_facts'),
        ({'network_verified': False}, 'network'),
        ({'dns_verified': False}, 'dns_clock'),
        ({'etcd_quorum_verified': False}, 'cluster_topology'),
        ({'exact_inventory_verified': False}, 'execution_scope'),
        ({'maker_checker_approval_verified': False}, 'approval'),
    ],
)
def test_each_critical_attestation_must_be_explicit_true(changed, gate_key) -> None:
    record = _job()
    record.result_summary_json.update(changed)
    report = build_kubespray_preflight(_connection(), jobs=[record], now=_NOW)
    assert report.state == 'blocked'
    assert any(gate.key == gate_key and gate.state == 'blocked' for gate in report.gates)


def test_production_and_unverified_git_source_are_blocked_even_with_host_evidence() -> None:
    prod = build_kubespray_preflight(_connection(environment='production'), jobs=[_job()], now=_NOW)
    assert prod.state == 'blocked'
    assert any(gate.key == 'target_classification' and gate.state == 'blocked' for gate in prod.gates)

    unverified = build_kubespray_preflight(_connection(source_checked=False), jobs=[_job()], now=_NOW)
    assert unverified.state == 'blocked'
    assert unverified.gates[0].state == 'blocked'


@pytest.mark.parametrize(
    ('changes', 'gate'),
    [
        ({'high_availability': True}, 'cluster_topology'),
        ({'upstream_kubespray_release': 'master'}, 'cluster_topology'),
        ({'kubernetes_minor': '1.37'}, 'cluster_topology'),
        ({'hosts': []}, 'host_facts'),
        ({'host_network_cidrs': []}, 'network'),
        ({'service_cidr': '10.233.64.0/18'}, 'network'),
        ({'pod_cidr': '172.16.10.0/24'}, 'network'),
        ({'service_cidr': 'not-a-cidr'}, 'network'),
        ({'pod_cidr': '127.0.0.0/8'}, 'network'),
        ({'pod_cidr': '0.0.0.0/0'}, 'network'),
        ({'service_cidr': '192.0.2.0/24'}, 'network'),
        ({'host_network_cidrs': ['::/0']}, 'network'),
        ({'host_network_cidrs': [None]}, 'network'),
    ],
)
def test_unsupported_topology_or_cidr_fails_closed(changes, gate) -> None:
    record = _job()
    record.result_summary_json.update(changes)
    report = build_kubespray_preflight(_connection(), jobs=[record], now=_NOW)
    assert report.state == 'blocked'
    assert any(item.key == gate and item.state == 'blocked' for item in report.gates)


def test_duplicate_host_identity_unsupported_os_and_missing_capacity_are_blocked() -> None:
    for change in (
        lambda hosts: hosts[1].update(asset_id=hosts[0]['asset_id']),
        lambda hosts: hosts[1].update(os_distribution='Windows'),
        lambda hosts: hosts[0].update(cpu_count=0),
        lambda hosts: hosts[0].update(asset_identity_verified=False),
        lambda hosts: hosts[0].update(role='worker'),
        lambda hosts: hosts[0].update(role=[]),
        lambda hosts: hosts[0].update(os_distribution=[]),
        lambda hosts: hosts[0].update(memory_mib=1024),
        lambda hosts: hosts[0].update(disk_gib=20),
        lambda hosts: hosts[0].update(cpu_count=True),
    ):
        record = _job()
        change(record.result_summary_json['hosts'])
        report = build_kubespray_preflight(_connection(), jobs=[record], now=_NOW)
        assert report.state == 'blocked'
        assert any(gate.key == 'host_facts' and gate.state == 'blocked' for gate in report.gates)


def test_later_failed_or_running_preflight_invalidates_older_success() -> None:
    older = _job(public_id='old-success', completed_at=_NOW - timedelta(minutes=10))
    for status in ('failed', 'running', 'cancel_requested', 'expired'):
        current = _job(public_id='new-attempt', status=status, completed_at=_NOW - timedelta(minutes=1))
        report = build_kubespray_preflight(_connection(), jobs=[current, older], now=_NOW)
        assert report.state == 'blocked'
        assert report.facts_job_public_id is None


def test_latest_mismatched_source_or_stale_preflight_never_reuses_prior_success() -> None:
    older = _job(public_id='old-success', completed_at=_NOW - timedelta(minutes=10))
    for current in (
        _job(public_id='wrong-source', result_summary_json={'repository': REPOSITORY}),
        _job(public_id='stale', completed_at=_NOW - timedelta(minutes=20)),
    ):
        report = build_kubespray_preflight(_connection(), jobs=[current, older], now=_NOW)
        assert report.state == 'blocked'
        assert report.facts_job_public_id is None


def test_future_worker_evidence_cannot_self_authorize_execution_or_maker_checker() -> None:
    record = _job()
    record.result_summary_json.update(
        worker_execution_admitted=True,
        plan_fingerprint_verified=True,
        maker_checker_approval_verified=True,
        maintenance_window_verified=True,
    )
    report = build_kubespray_preflight(_connection(), jobs=[record], now=_NOW)
    assert report.state == 'ready_for_review'
    assert [gate.state for gate in report.gates[-2:]] == ['blocked', 'blocked']
    assert all('approved' not in key for key in report.presentation() if key != 'gates')
