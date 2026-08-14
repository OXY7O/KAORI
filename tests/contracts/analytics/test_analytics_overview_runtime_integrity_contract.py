from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_overview_section_registry_has_one_composite_owner_and_no_legacy_endpoints() -> None:
    registry = read('app/analytics/kubernetes/overview/sections.py')
    routes = read('app/analytics/routes.py')
    index = read('app/templates/analytics/kubernetes/overview/index.html')

    assert "'health-summary'" in registry
    assert "hydration='composite'" in registry
    assert "'prometheus-status'" not in registry
    assert "'hero-posture'" not in registry
    assert "'actionable-recommendations'" not in registry
    assert "'recommendations': OverviewSection" not in registry
    assert '_composite_tabs_oob.html' in routes
    assert "'composite'" in index
    assert 'data-overview-composite-dependent="true"' in index


def test_overview_tabs_load_only_on_first_activation() -> None:
    index = read('app/templates/analytics/kubernetes/overview/index.html')
    runtime = read('app/static/js/analytics/kubernetes/controls.js')

    assert 'hx-trigger="kaori:analytics-tab-activated once"' in index
    assert 'loads its committed snapshot only when the tab is first activated' in index
    assert "window.htmx.trigger(target, 'kaori:analytics-tab-activated')" in runtime
    assert 'hx-trigger="load"' not in index


def test_overview_snapshot_scope_is_parameter_exact() -> None:
    summary = read('app/analytics/kubernetes/overview/snapshot_summary.py')

    assert "'analytics.capacity': {**cluster_scope, 'time_range': time_range}" in summary
    assert "'analytics.workload': {**cluster_scope, 'time_range': time_range}" in summary
    assert "'analytics.forecast': {**cluster_scope, 'history_window': forecast_history_window}" in summary
    assert "'analytics.alerts': {**cluster_scope, 'source': 'auto'}" in summary
    assert 'actual == expected' in summary
    assert "'datasets': dataset_states" in summary
    assert "'missing_dataset_count':" in summary


def test_workload_overview_propagates_selected_time_range() -> None:
    service = read('app/analytics/kubernetes/overview/service.py')

    assert 'def _get_workload_snapshot(*, cluster_id: str, time_range: str)' in service
    workload_call = service[
        service.index('def _get_workload_snapshot') : service.index('def _get_top_consumers_snapshot')
    ]
    assert 'time_range=time_range' in workload_call


def test_unavailable_domain_snapshots_return_none_not_synthetic_zero_payloads() -> None:
    expectations = {
        'app/analytics/kubernetes/utilization/service.py': 'if not isinstance(summary, dict):\n        return None',
        'app/analytics/kubernetes/capacity/service.py': 'if not isinstance(capacity_summary, dict):\n        return None',
        'app/analytics/kubernetes/storage/service.py': 'if not storage_summary:\n        return None',
        'app/analytics/kubernetes/workload/service.py': 'if not result.available:\n        return None',
        'app/analytics/kubernetes/top_consumers/service.py': 'if not is_current_payload(payload):\n        return None',
        'app/analytics/kubernetes/forecast/presentation.py': 'if not isinstance(forecast_payload, dict):\n        return None',
        'app/analytics/kubernetes/alerts/snapshots.py': 'if not result.available:\n        return None',
    }
    removed_adapters = {
        'app/analytics/kubernetes/utilization/service.py': '_empty_utilization_snapshot',
        'app/analytics/kubernetes/capacity/service.py': '_empty_capacity_snapshot',
        'app/analytics/kubernetes/storage/service.py': '_empty_storage_snapshot',
        'app/analytics/kubernetes/workload/service.py': '_empty_workload_snapshot',
        'app/analytics/kubernetes/top_consumers/service.py': '_empty_top_consumers_snapshot',
        'app/analytics/kubernetes/forecast/presentation.py': '_empty_forecast_snapshot',
        'app/analytics/kubernetes/alerts/snapshots.py': '_empty_alerts_snapshot',
    }
    for path, marker in expectations.items():
        source = read(path)
        assert marker in source
        assert removed_adapters[path] not in source


def test_overview_unknown_semantics_prevent_false_healthy_zero_states() -> None:
    schema = read('app/analytics/kubernetes/overview/schema.py')
    health_service = read('app/analytics/kubernetes/overview/health.py')
    health_template = read('app/templates/analytics/kubernetes/overview/partials/_health_summary.html')

    assert "'available': False" in schema
    assert "value='N/A'" in schema
    assert "_signal('Limited', 'warning', 'amber'" in health_service
    assert "_signal('N/A', 'unknown', 'gray'" in health_service
    assert 'if not evidence.evidence_available:' in health_service
    assert 'Operational Posture Cannot Be Confirmed Yet' in health_template


def test_overview_scoped_links_preserve_existing_query_strings() -> None:
    macro = read('app/templates/analytics/kubernetes/components/_scoped_link.html')
    alerts = read('app/templates/analytics/kubernetes/overview/partials/_alerts_snapshot.html')
    summary = read('app/templates/analytics/kubernetes/overview/partials/_actionable_recommendation_summary.html')

    assert "'&' if '?' in base_href else '?'" in macro
    assert 'scoped_link.href(alerts.href' in alerts
    assert 'scoped_link.href(source.href' in summary
    assert "alerts.href ~ '?cluster_id='" not in alerts


def test_overview_legacy_templates_are_removed() -> None:
    assert not Path('app/templates/analytics/components/_overview_surfaces.html').exists()
    assert not Path('app/templates/analytics/kubernetes/overview/partials/_prometheus_status.html').exists()
    assert not Path('app/templates/analytics/kubernetes/overview/partials/_prometheus_status_loading.html').exists()
    assert not Path('app/analytics/kubernetes/common/cache.py').exists()


def test_overview_prioritized_actions_require_evidence_and_actionable_findings() -> None:
    service = read('app/analytics/kubernetes/overview/service.py')

    assert "evidence_complete = bool(payload['actionable_recommendations'].get('evidence_complete', False))" in service
    assert "has_actionable_findings = payload['actionable_recommendation_count'] > 0" in service
    assert "if bool(recommendation.get('is_actionable', False))" in service
    assert "payload['recommendations'] = []" in service
