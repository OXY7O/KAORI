from types import SimpleNamespace

from app.integrations.overview_extensions import build_overview_stats
from app.integrations.service import (
    _capability_attention_display,
    _coverage_stats,
    _runtime_scope_label,
    _runtime_stats,
)


def test_capability_attention_copy_handles_zero_one_and_many() -> None:
    assert _capability_attention_display(0) == 'No Capability Attention'
    assert _capability_attention_display(1) == '1 Item Needs Attention'
    assert _capability_attention_display(3) == '3 Items Need Attention'


def test_runtime_scope_label_describes_active_filters() -> None:
    assert _runtime_scope_label(integration_type='', health='', readiness='') == 'All Registered Targets'
    assert (
        _runtime_scope_label(
            integration_type='metrics_source',
            health='not_observed',
            readiness='validation_required',
        )
        == 'Metrics Sources · Not Observed · Validation Required'
    )


def test_runtime_stats_are_calculated_from_the_supplied_scope() -> None:
    rows = [
        {'health_status': 'healthy', 'capability_attention': 0},
        {'health_status': 'not_observed', 'capability_attention': 1},
    ]
    assert _runtime_stats(rows) == {
        'total': 2,
        'healthy': 1,
        'degraded': 0,
        'unhealthy': 0,
        'not_observed': 1,
        'capability_attention': 1,
    }


def test_portfolio_stats_separate_validation_and_missing_configuration() -> None:
    kubernetes = [
        SimpleNamespace(
            readiness_status='ready',
            integration_instance=SimpleNamespace(enabled=True),
        )
    ]
    metrics_sources = [
        SimpleNamespace(endpoint='https://prometheus.example', enabled=True, readiness_status='degraded'),
        SimpleNamespace(endpoint='', enabled=True, readiness_status='validation_required'),
    ]
    alertmanager = [
        SimpleNamespace(endpoint='https://alertmanager.example', enabled=True, readiness_status='blocked'),
    ]

    result = build_overview_stats(
        kubernetes_connections=kubernetes,
        metrics_sources=metrics_sources,
        alertmanager_instances=alertmanager,
        extension_instances=[],
    )

    assert result == {
        'total': 4,
        'configured': 3,
        'ready': 1,
        'validation_required': 2,
        'not_configured': 1,
        'attention': 3,
        'blocked': 1,
    }


def test_coverage_stats_separate_available_and_planned_domains() -> None:
    rows = [
        {
            'lifecycle': 'available',
            'configured': 3,
            'ready': 2,
            'attention': 1,
        },
        {
            'lifecycle': 'available',
            'configured': 2,
            'ready': 1,
            'attention': 2,
        },
        {
            'lifecycle': 'planned',
            'configured': 0,
            'ready': 0,
            'attention': 0,
        },
    ]

    assert _coverage_stats(rows) == {
        'available_domains': 2,
        'planned_domains': 1,
        'configured_targets': 5,
        'ready_targets': 3,
        'attention_targets': 3,
    }
