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
    assert report.verified_gates == report.required_gates == 10
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
