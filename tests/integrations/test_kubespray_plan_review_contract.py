"""Review-only Kubernetes Plan must come from exact, fresh committed evidence.

No host, SSH, Runner, Celery or Kubernetes access is required by this module.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.infrastructure_automation.kubernetes.kubespray_preflight import KUBESPRAY_COMMIT
from app.infrastructure_automation.kubernetes.plan_review import (
    PLAN_RESULT_TYPE,
    build_kubespray_plan_review,
)
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)

_NOW = datetime(2026, 11, 16, 4, 0, tzinfo=UTC)


def _connection() -> SimpleNamespace:
    return SimpleNamespace(
        id=5,
        integration_type='configuration_automation',
        provider_key='ansible',
        environment='laboratory',
        enabled=True,
        lifecycle_status='active',
        metadata_json={
            'source_repository': REPOSITORY,
            'source_sha': SOURCE_CANDIDATE_SHA,
            'execution_environment_digest': 'sha256:' + 'a' * 64,
            'profile_key': PROFILE_KEY,
            'ansible_core_version': ANSIBLE_CORE_VERSION,
            'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
            'kubespray_release': KUBESPRAY_RELEASE,
            'source_validation': {
                'status': 'source_checked',
                'repository': REPOSITORY,
                'revision': SOURCE_CANDIDATE_SHA,
                'profile_key': PROFILE_KEY,
                'checked_files': 5,
                'operation_authorized': False,
            },
        },
    )


def _host(i: int) -> dict:
    return {
        'asset_id': f'lab-asset-{i}',
        'asset_identity_verified': True,
        'role': 'control_plane' if i == 1 else 'worker',
        'os_distribution': 'Ubuntu',
        'os_release': '24.04',
        'cpu_count': 4,
        'memory_mib': 8192,
        'disk_gib': 100,
        'address': f'192.168.50.{i + 10}',
    }


def _job() -> SimpleNamespace:
    return SimpleNamespace(
        id=9,
        public_id='preflight-canonical-9',
        integration_instance_id=5,
        integration_type='configuration_automation',
        job_type='infrastructure_automation',
        operation='automation_kubespray_host_preflight',
        result_type='automation_kubespray_host_preflight_v1',
        queue_name='automation',
        status='succeeded',
        completed_at=_NOW - timedelta(minutes=2),
        result_summary_json={
            'repository': REPOSITORY,
            'source_sha': SOURCE_CANDIDATE_SHA,
            'execution_environment_digest': 'sha256:' + 'a' * 64,
            'upstream_kubespray_commit': KUBESPRAY_COMMIT,
            'upstream_kubespray_release': 'v2.32.0',
            'kubernetes_minor': '1.36',
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
            'high_availability': False,
            'pod_cidr': '10.233.0.0/18',
            'service_cidr': '10.233.64.0/18',
            'host_network_cidrs': ['192.168.50.0/24'],
            'hosts': [_host(i) for i in range(1, 4)],
        },
    )


def test_plan_result_is_deterministic_review_only_and_excludes_raw_inventory() -> None:
    connection, job = _connection(), _job()
    first = build_kubespray_plan_review(connection, job, now=_NOW)
    second = build_kubespray_plan_review(connection, deepcopy(job), now=_NOW + timedelta(seconds=1))

    assert first.status == 'requires_independent_approval'
    assert first.plan_fingerprint == second.plan_fingerprint
    assert first.plan_fingerprint and len(first.plan_fingerprint) == 64
    assert first.inventory_fingerprint and len(first.inventory_fingerprint) == 64
    assert first.mutation_authorized is False
    assert first.host_preflight_job_public_id == job.public_id
    summary = first.committed_summary()
    assert summary['schema_version'] == 1
    assert summary['execution_environment_digest'] == 'sha256:' + 'a' * 64
    assert summary['approval_status'] == 'not_requested'
    assert summary['execution_status'] == 'blocked'
    assert summary['mutation_authorized'] is False
    assert PLAN_RESULT_TYPE == 'automation_kubespray_plan_review_v1'
    assert '192.168.' not in repr(summary)
    assert 'lab-asset-' not in repr(summary)
    assert 'credential_reference' not in repr(summary)


@pytest.mark.parametrize(
    'mutate',
    [
        lambda conn, job: conn.metadata_json.update(source_sha='f' * 40),
        lambda conn, job: conn.metadata_json.update(execution_environment_digest=None),
        lambda conn, job: conn.metadata_json.update(execution_environment_digest='not-a-digest'),
        lambda conn, job: job.result_summary_json.update(execution_environment_digest='sha256:' + 'b' * 64),
        lambda conn, job: conn.metadata_json['source_validation'].update(status='blocked'),
        lambda conn, job: setattr(conn, 'environment', 'production'),
        lambda conn, job: setattr(conn, 'enabled', False),
        lambda conn, job: setattr(conn, 'lifecycle_status', 'disabled'),
        lambda conn, job: setattr(conn, 'provider_key', 'harbor'),
        lambda conn, job: setattr(job, 'status', 'failed'),
        lambda conn, job: setattr(job, 'queue_name', 'default'),
        lambda conn, job: setattr(job, 'integration_instance_id', 6),
        lambda conn, job: job.result_summary_json.update(upstream_kubespray_commit='0' * 40),
        lambda conn, job: job.result_summary_json.update(host_keys_verified=False),
        lambda conn, job: job.result_summary_json.update(service_cidr='10.233.0.0/18'),
        lambda conn, job: job.result_summary_json['hosts'][1].update(address='10.233.12.20'),
        lambda conn, job: job.result_summary_json['hosts'][0].update(asset_id='lab-asset-2'),
        lambda conn, job: job.result_summary_json['hosts'][1].pop('address'),
    ],
)
def test_untrusted_source_inventory_or_policy_never_generates_review_plan(mutate) -> None:
    connection, job = _connection(), _job()
    mutate(connection, job)
    review = build_kubespray_plan_review(connection, job, now=_NOW)
    assert review.status == 'blocked'
    assert review.plan_fingerprint is None
    assert review.mutation_authorized is False


def test_plan_expires_at_exact_preflight_freshness_boundary() -> None:
    connection, job = _connection(), _job()
    review = build_kubespray_plan_review(connection, job, now=job.completed_at + timedelta(minutes=15))
    assert review.status == 'blocked'
    assert review.plan_fingerprint is None


def test_plan_fingerprint_changes_with_new_committed_preflight_and_target() -> None:
    connection, job = _connection(), _job()
    original = build_kubespray_plan_review(connection, job, now=_NOW)
    replacement = deepcopy(job)
    replacement.public_id = 'preflight-canonical-10'
    replacement.result_summary_json['hosts'][2]['address'] = '192.168.50.99'
    changed = build_kubespray_plan_review(connection, replacement, now=_NOW)
    assert changed.status == 'requires_independent_approval'
    assert changed.plan_fingerprint != original.plan_fingerprint


def test_worker_self_approval_fields_are_never_included_in_review_result() -> None:
    connection, job = _connection(), _job()
    job.result_summary_json.update(
        maker_checker_approval_verified=True,
        worker_execution_admitted=True,
        maintenance_window_verified=True,
        ssh_private_key='do-not-echo-this',
    )
    result = build_kubespray_plan_review(connection, job, now=_NOW)
    assert result.status == 'requires_independent_approval'
    assert result.committed_summary()['approval_status'] == 'not_requested'
    assert 'do-not-echo-this' not in repr(result.committed_summary())
