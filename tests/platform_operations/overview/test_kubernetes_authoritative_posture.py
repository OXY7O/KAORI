from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.platform_operations.overview import presentation


@pytest.mark.parametrize(
    ('label', 'tone'),
    [
        ('Setup Required', 'warning'),
        ('Global Gate Disabled', 'warning'),
        ('Partial Readiness', 'warning'),
        ('Policy Required', 'warning'),
        ('Policy Scope Review', 'warning'),
        ('Verification Required', 'warning'),
    ],
)
def test_overview_uses_kubernetes_administration_posture(monkeypatch, label, tone):
    """Counts alone must never turn an authoritative Kubernetes warning into Ready."""
    domain = {
        'cluster_count': 1,
        'ready_cluster_count': 1,
        'enabled_namespace_count': 0,
        'global_reveal_enabled': True,
        'administration_status_label': label,
        'administration_status_tone': tone,
        'administration_status_detail': 'Authority requires review.',
    }
    monkeypatch.setattr(
        presentation, 'build_kubernetes_administration_summary', lambda: domain
    )
    context = presentation.build_platform_operations_overview_context(
        can_jobs=False, can_data_lifecycle=False, can_kubernetes_admin=True
    )

    assert len(context['workspaces']) == 1
    assert context['workspaces'][0]['status_label'] == label
    assert context['workspaces'][0]['status_tone'] == tone
    assert context['overall_status_label'] == 'Review Required'
    assert context['overall_status_tone'] == 'warning'
