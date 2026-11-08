from types import SimpleNamespace

import pytest

from app.kubernetes.inventory.resources.nodes import (
    _node_os_family,
    _node_table_row,
    _platform_detail,
)


@pytest.mark.parametrize(
    ('reported_os', 'labels', 'expected'),
    [
        ('linux', {}, 'Linux'),
        ('LINUX', {}, 'Linux'),
        ('windows', {}, 'Windows'),
        ('freebsd', {}, 'FreeBSD'),
        ('OpenBSD', {}, 'OpenBSD'),
        ('netbsd', {}, 'NetBSD'),
        ('darwin', {}, 'Darwin'),
        (None, {'kubernetes.io/os': 'windows'}, 'Windows'),
        (None, {}, 'Not Reported'),
    ],
)
def test_node_os_family_only_uses_committed_os_evidence(
    reported_os: str | None, labels: dict[str, str], expected: str
) -> None:
    node = SimpleNamespace(
        operating_system=reported_os,
        labels=labels,
        os_image='Debian GNU/Linux 13 (trixie)',
        container_runtime='containerd://1.7.9',
    )

    assert _node_os_family(node) == expected
    assert _platform_detail(SimpleNamespace(**vars(node), architecture='amd64'))['operating_system_display'] == expected


def test_node_table_subtitle_uses_family_not_os_image_or_runtime() -> None:
    node = SimpleNamespace(
        id=7,
        node_name='worker-1',
        operating_system='linux',
        labels={'kubernetes.io/os': 'linux'},
        os_image='Debian GNU/Linux 13 (trixie)',
        container_runtime='containerd://1.7.9',
        role='worker',
        status='Ready',
        unschedulable=False,
        memory_pressure=False,
        disk_pressure=False,
        pid_pressure=False,
        network_unavailable=False,
        cpu=16,
        memory='32768Mi',
        ephemeral_storage='102400Mi',
        internal_ip='10.0.0.7',
        external_ip=None,
    )

    result = _node_table_row(node, 'Kubernetes X300', 'Development')

    assert result['node_name'] == 'worker-1'
    assert result['identity_supporting'] == 'Linux'
    assert 'Debian' not in result['identity_supporting']
    assert 'containerd' not in result['identity_supporting']
    assert result['cluster_name'] == 'Kubernetes X300'


def test_missing_os_does_not_guess_family_from_linux_distribution_image() -> None:
    node = SimpleNamespace(
        operating_system=None,
        labels={},
        os_image='Ubuntu 24.04 LTS',
        container_runtime='containerd://2.0',
    )
    assert _node_os_family(node) == 'Not Reported'
