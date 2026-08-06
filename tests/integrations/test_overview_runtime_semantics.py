from types import SimpleNamespace

from app.integrations.service import (
    _capability_attention_display,
    _overview_stats,
    _runtime_scope_label,
    _runtime_stats,
)


def test_capability_attention_copy_handles_zero_one_and_many() -> None:
    assert _capability_attention_display(0) == 'No Capability Attention'
    assert _capability_attention_display(1) == '1 Item Needs Attention'
    assert _capability_attention_display(3) == '3 Items Need Attention'


def test_runtime_scope_label_describes_active_filters() -> None:
    assert _runtime_scope_label(provider='', health='', readiness='') == 'All Registered Targets'
    assert (
        _runtime_scope_label(
            provider='prometheus',
            health='not_observed',
            readiness='validation_required',
        )
        == 'Prometheus / Thanos · Not Observed · Validation Required'
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
    kubernetes = [SimpleNamespace(readiness_status='ready')]
    prometheus = [
        SimpleNamespace(endpoint='https://prometheus.example', readiness_status='degraded'),
        SimpleNamespace(endpoint='', readiness_status='validation_required'),
    ]
    alertmanager = [
        SimpleNamespace(endpoint='https://alertmanager.example', readiness_status='blocked'),
    ]

    result = _overview_stats(
        kubernetes_connections=kubernetes,
        prometheus_instances=prometheus,
        alertmanager_instances=alertmanager,
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
