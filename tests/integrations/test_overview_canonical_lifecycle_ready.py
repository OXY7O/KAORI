"""Overview Ready must require active canonical lifecycle for every provider type."""

from types import SimpleNamespace

import pytest

from app.integrations.overview_extensions import (
    build_overview_stats,
    build_provider_portfolio_counts,
    canonical_operational,
    effective_runtime_readiness,
)


@pytest.mark.parametrize(
    ('enabled', 'lifecycle', 'allowed'),
    [
        (True, 'active', True),
        (False, 'active', False),
        (True, 'disabled', False),
        (True, 'deleting', False),
    ],
)
def test_canonical_readiness_gate(enabled, lifecycle, allowed):
    canonical = SimpleNamespace(enabled=enabled, lifecycle_status=lifecycle)
    connection = SimpleNamespace(
        integration_instance=canonical,
        readiness_status='ready',
    )
    assert canonical_operational(connection, kubernetes=True) is allowed
    assert effective_runtime_readiness(connection, kubernetes=True) == ('ready' if allowed else 'blocked')


@pytest.mark.parametrize('lifecycle', ['disabled', 'deleting'])
def test_all_kpi_and_catalog_provider_ready_exclude_inactive_canonical(lifecycle):
    can = SimpleNamespace(enabled=True, lifecycle_status=lifecycle)
    kubernetes = [SimpleNamespace(integration_instance=can, readiness_status='ready')]
    metrics = [
        SimpleNamespace(
            endpoint='https://metrics.invalid',
            integration_instance=can,
            enabled=True,
            readiness_status='ready',
        )
    ]
    alerts = [
        SimpleNamespace(
            endpoint='https://alert.invalid',
            integration_instance=can,
            enabled=True,
            readiness_status='ready',
        )
    ]
    generic = [
        SimpleNamespace(
            integration_type='object_storage',
            enabled=True,
            lifecycle_status=lifecycle,
            readiness_status='ready',
        )
    ]
    stats = build_overview_stats(
        kubernetes_connections=kubernetes,
        metrics_sources=metrics,
        alertmanager_instances=alerts,
        extension_instances=generic,
    )
    assert stats['total'] == 4
    assert stats['ready'] == 0
    assert stats['readiness_review'] == 4
    counts = build_provider_portfolio_counts(
        kubernetes_connections=kubernetes,
        metrics_sources=metrics,
        alertmanager_instances=alerts,
        extension_instances=generic,
    )
    for key in ('container_orchestrator', 'metrics_source', 'alert_source', 'object_storage'):
        assert counts[key]['ready'] == 0
        assert counts[key]['disabled'] == 1


def test_only_canonical_active_ready_targets_count_ready():
    can = SimpleNamespace(enabled=True, lifecycle_status='active')
    enabled = SimpleNamespace(
        endpoint='https://source.invalid', enabled=True, integration_instance=can, readiness_status='ready'
    )
    stats = build_overview_stats(
        kubernetes_connections=[], metrics_sources=[enabled], alertmanager_instances=[], extension_instances=[]
    )
    assert stats['ready'] == 1
