from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.kubernetes.inventory.resources.pods import _pod_list_row, _pod_owner_summary


def _pod(
    *,
    owner_kind: str | None = 'Deployment',
    owner_name: str | None = 'minio',
    details: dict | None = None,
    ready: str | None = '1/1',
    restarts: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        namespace='monitoring',
        pod_name='pod-demo',
        node_name='worker-1',
        pod_ip='10.10.0.7',
        ready=ready,
        phase='Running',
        workload_type=owner_kind,
        workload_name=owner_name,
        restart_count=restarts,
        created_at=datetime(2026, 10, 1, tzinfo=UTC),
        container_names=['app'],
        details=details if details is not None else {
            'owner_resolution': {'direct_kind': owner_kind, 'direct_name': owner_name},
            'runtime_evidence_reported': True,
            'specification_evidence_reported': True,
        },
    )


@pytest.mark.parametrize(
    ('kind', 'name', 'annotations', 'expected_kind', 'expected_name'),
    [
        ('Deployment', 'minio', {}, 'Deployment', 'minio'),
        (
            'StatefulSet',
            'alertmanager-kaori-monitoring-kube-prom-alertmanager',
            {},
            'StatefulSet',
            'alertmanager-kaori-monitoring-kube-prom-alertmanager',
        ),
        ('DaemonSet', 'node-exporter', {}, 'DaemonSet', 'node-exporter'),
        ('Job', 'minio-create-thanos-bucket-2024', {}, 'Job', 'minio-create-thanos-bucket-2024'),
        ('CronJob', 'periodic-backup', {}, 'CronJob', 'periodic-backup'),
        ('ReplicaSet', 'pod-controller-xyz', {}, 'ReplicaSet', 'pod-controller-xyz'),
        ('Node', 'desktop-control-plane', {}, 'Node-owned', 'desktop-control-plane'),
        (
            'Node',
            'desktop-control-plane',
            {'kubernetes.io/config.mirror': 'mirror-hash'},
            'Static Pod',
            'desktop-control-plane',
        ),
        (None, None, {}, 'Standalone', 'No controller owner'),
        ('Deployment', None, {}, 'Deployment', 'Owner name not reported'),
    ],
)
def test_pod_owner_kind_uses_observed_controller_and_mirror_evidence(
    kind: str | None,
    name: str | None,
    annotations: dict[str, str],
    expected_kind: str,
    expected_name: str,
) -> None:
    pod = _pod(
        owner_kind=kind,
        owner_name=name,
        details={'owner_resolution': {}, 'annotations': annotations},
    )
    assert _pod_owner_summary(pod, pod.details) == (expected_kind, expected_name)


def test_owner_not_reported_is_not_misclassified_as_unmanaged() -> None:
    pod = _pod(owner_kind=None, owner_name=None, details={})
    assert _pod_owner_summary(pod, pod.details) == (
        'Owner Not Reported',
        'Owner evidence unavailable',
    )


@pytest.mark.parametrize(
    ('count', 'reported', 'expected'),
    [
        (0, True, 'Restarts · 0'),
        (1, True, 'Restarts · 1'),
        (7, True, 'Restarts · 7'),
        (25, True, 'Restarts · 25'),
        (0, False, 'Restarts · Not Reported'),
        (25, False, 'Restarts · Not Reported'),
    ],
)
def test_restart_summary_preserves_cumulative_evidence_without_severity(
    count: int,
    reported: bool,
    expected: str,
) -> None:
    pod = _pod(
        restarts=count,
        details={
            'owner_resolution': {'direct_kind': 'Deployment', 'direct_name': 'minio'},
            'runtime_evidence_reported': reported,
            'specification_evidence_reported': True,
        },
    )
    row = _pod_list_row(pod, 'Kubernetes X300', 'Development')
    assert row['owner_kind_label'] == 'Deployment'
    assert row['owner_name_display'] == 'minio'
    assert row['restart_summary'] == expected
    assert row['owner_display'] == 'Deployment · minio'
    assert row['restarts'] == count
    assert 'severity' not in row


def test_long_controller_name_keeps_full_identity_in_row_dto() -> None:
    name = 'alertmanager-kaori-monitoring-kube-prom-alertmanager'
    pod = _pod(owner_kind='StatefulSet', owner_name=name)
    row = _pod_list_row(pod, 'Kubernetes X300', 'Development')
    assert row['owner_name_display'] == name
    assert row['owner_kind_label'] == 'StatefulSet'
