"""Cross-domain render contract for the canonical KAORI Analytics presentation."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.common.analytics.params import get_allowed_time_ranges

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
        autoescape=True,
    )
    def _user_datetime(value: object, default: str = 'Unavailable') -> str:
        return str(value) if value else default

    env.filters['user_datetime'] = _user_datetime

    def _url_for(endpoint: str, **kwargs: object) -> str:
        return '/analytics/' + endpoint.replace('.', '/')

    env.globals['url_for'] = _url_for
    return env


def _k8s_payload() -> dict:
    signal = {
        'tone': 'normal',
        'status': 'normal',
        'icon': 'circle-check',
        'label': 'Health',
        'value': 'Normal',
        'description': 'Committed evidence is available.',
    }
    return {
        'clusters': [{'id': 7, 'name': 'Kubernetes X300'}],
        'selected_cluster_id': 7,
        'selected_time_range': '24h',
        'allowed_time_ranges': get_allowed_time_ranges(),
        'metrics_source': {
            'status_label': 'Query Ready',
            'connected': True,
            'configured': True,
            'response_time_ms': 23,
            'checked_at': None,
        },
        'snapshot_summary': {
            'status': 'Current',
            'tone': 'normal',
            'current_dataset_count': 7,
            'expected_dataset_count': 7,
        },
        'health_summary': {
            key: signal
            for key in (
                'cluster_health',
                'resource_pressure',
                'capacity_risk',
                'active_alerts',
                'forecast_risk',
                'top_risk_namespace',
            )
        },
    }


def _registry_payload() -> dict:
    return {
        'active_tab': 'overview',
        'provider_options': [{'id': 3, 'name': 'Harbor Primary'}],
        'selected_provider_id': 3,
        'snapshot_window': '24h',
        'time_range_options': get_allowed_time_ranges(),
        'alert_filters': {},
        'data_readiness': {
            'eligible_count': 1,
            'registered_count': 1,
            'covered_count': 1,
            'current_count': 1,
            'label': 'Current Snapshot',
            'tone': 'normal',
            'latest_generated_at': None,
            'latest_expiry_at': None,
            'last_attempt_label': 'Never',
            'helper': 'Current committed evidence.',
            'is_active': False,
            'execution_tone': 'normal',
            'collection_warning': None,
        },
    }


def test_shared_selector_and_readiness_geometry_render_identically_across_domains() -> None:
    env = _environment()
    k8s = env.get_template(
        'kubernetes/analytics/overview/partials/_health_summary.html'
    ).render(payload=_k8s_payload())
    registry = env.get_template(
        'artifact_registry/partials/_analytics_controls_readiness.html'
    ).render(analytics=_registry_payload())

    for html in (k8s, registry):
        assert html.count('data-analytics-controls-readiness') == 1
        assert html.count('data-analytics-source-status') == 1
        assert html.count('data-analytics-snapshot-status') == 1
        assert html.count('grid gap-4 sm:grid-cols-2') >= 1
        assert html.count('grid gap-4 lg:grid-cols-2') >= 1
        assert 'Analytics Controls &amp; Data Readiness' in html
        assert 'Latest Analytics Data Snapshot' in html
        assert 'Last 24 Hours' in html
        assert 'Last 60 Days' in html

    assert 'id="analytics-overview-cluster-filter"' in k8s
    assert 'name="cluster_id"' in k8s
    assert 'Kubernetes X300' in k8s
    assert 'data-analytics-metrics-source-status' in k8s
    assert 'Query Ready' in k8s
    assert '23 ms' in k8s
    assert 'Response' in k8s and 'Checked At' in k8s
    assert 'id="artifact-registry-analytics-provider"' in registry
    assert 'name="provider_id"' in registry
    assert 'Harbor Primary' in registry
    assert 'Registry Source Status' in registry
    assert 'title="Filters the generation age' in registry


def test_shared_selector_supports_legacy_bookmarks_without_duplicating_normal_options() -> None:
    env = _environment()
    template = env.from_string(
        '{% import "analytics/components/_controls_readiness.html" as controls %}'
        '{{ controls.selector("range", "snapshot_window", "Time Range", '
        'options, selected, legacy_value="current", '
        'legacy_label="Latest Snapshot (Any Age)") }}'
    )
    latest = template.render(options=get_allowed_time_ranges(), selected='24h')
    historical = template.render(options=get_allowed_time_ranges(), selected='current')

    assert latest.count('<option') == 7
    assert historical.count('<option') == 8
    assert 'Latest Snapshot (Any Age)' not in latest
    assert 'Latest Snapshot (Any Age)' in historical
    assert 'value="24h"' in latest
    assert 'selected' in latest


def test_kubernetes_metrics_status_preserves_source_specific_query_evidence() -> None:
    env = _environment()
    source = env.from_string(
        '{% import "kubernetes/analytics/components/_metrics_source_status.html" as k8s %}'
        '{{ k8s.render(status) }}'
    )
    base = {'configured': True, 'connected': True, 'response_time_ms': 16}
    for delta, expected in (
        ({}, 'Query Ready'),
        ({'observation_degraded': True}, 'Query Degraded'),
        ({'connected': False}, 'Unavailable'),
        ({'configured': False, 'connected': False}, 'Not Configured'),
    ):
        html = source.render(status={**base, **delta})
        assert expected in html
        assert 'data-analytics-metrics-source-status' in html
        assert 'data-analytics-source-status' in html
        assert 'Response' in html
        assert 'Checked At' in html


def test_future_provider_does_not_require_a_domain_specific_selector_component() -> None:
    env = _environment()
    template = env.from_string(
        '{% import "analytics/components/_controls_readiness.html" as controls %}'
        '{% call controls.controls_grid() %}'
        '{{ controls.selector("provider", "provider_id", "Provider", providers, selected) }}'
        '{% endcall %}'
    )
    html = template.render(
        providers=[{'id': 'provider-4', 'name': 'Future Object Storage Provider'}],
        selected='provider-4',
    )
    assert 'Future Object Storage Provider' in html
    assert 'name="provider_id"' in html
    assert 'grid gap-4 sm:grid-cols-2' in html
