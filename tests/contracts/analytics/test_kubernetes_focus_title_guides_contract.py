"""#4746: Focused Kubernetes Analytics Guides and concise Overview review text."""

import re
from pathlib import Path

from jinja2 import Environment

ROOT = Path('app/templates/kubernetes/analytics')
SHARED = Path('app/templates/kubernetes/analytics/components/_analysis_workspace.html')

FOCUS = {
    'utilization': ('partials/_readiness_scope.html', 'partials/_overview.html', 'index.html'),
    'capacity': ('partials/_controls_readiness.html', 'partials/_overview.html', 'index.html'),
    'workload': ('partials/_controls_readiness.html', 'partials/_overview.html', 'index.html'),
    'storage': ('partials/_controls_readiness.html', 'partials/_overview.html', 'partials/_storage_section.html'),
    'top_consumers': ('partials/_controls_readiness.html', 'partials/_summary.html', 'partials/_top_consumers_section.html'),
    'forecast': ('partials/_controls_readiness.html', 'partials/_overview_methodology.html', 'partials/_forecast_section.html'),
    'alerts': ('partials/_filters.html', 'partials/_cluster_signal_overview.html', 'index.html'),
}
CONTENT = {
    'utilization': (
        '_current_summary.html',
        '_trend.html',
        '_node_detail.html',
        '_recommendations.html',
    ),
    'capacity': (
        '_worker_summary.html',
        '_allocation.html',
        '_risk.html',
        '_recommendations.html',
    ),
    'workload': (
        '_tenant_quota_section.html',
        '_workload_mapping_section.html',
        '_recommendations.html',
    ),
    'storage': (
        '_capacity_utilization_panel.html',
        '_filesystem_panel.html',
        '_persistent_volume_claims_panel.html',
        '_persistent_volumes_panel.html',
        '_recommendations.html',
    ),
    'top_consumers': ('_top_consumers_section.html', '_consumer_detail_section.html'),
    'forecast': ('_forecast_section.html',),
    'alerts': (
        '_alerts_table.html',
        '_anomalies_table.html',
        '_routing_summary.html',
        '_silence_inhibition_summary.html',
        '_ownership_summary.html',
        '_incident_readiness.html',
        '_recommendations.html',
        '_operational_resources.html',
    ),
}


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_shared_focus_macros_accept_optional_title_accessory_without_changing_tabs() -> None:
    source = read(SHARED)
    Environment(autoescape=True).parse(source)

    assert "eyebrow='Analysis Controls', title_accessory=''" in source
    assert "badge_text='Overview', title_accessory=''" in source
    assert "detached=false, title_accessory=''" in source
    assert 'eyebrow=eyebrow, title_accessory=title_accessory' in source
    assert source.count('{{ title_accessory }}') == 2
    assert 'content_tabs.render_buttons(' in source
    assert 'data-analytics-tabset-id="{{ tabset_id }}"' in source


def test_all_focused_analytics_routes_have_title_owned_guides() -> None:
    environment = Environment(autoescape=True)
    for domain, locations in FOCUS.items():
        for location in locations:
            path = ROOT / domain / location
            source = read(path)
            environment.parse(source)
            assert 'components/info_tip.html' in source, path
            assert 'info_tip.render(' in source, path
            assert "variant='guide'" in source, path
            assert "placement='right'" in source, path
        controls, overview, workspace = (read(ROOT / domain / p) for p in locations)
        if domain != 'alerts':
            assert 'title_accessory=info_tip.render(' in controls
        if domain not in {'alerts', 'top_consumers'}:
            assert 'title_accessory=info_tip.render(' in overview
        assert (
            'title_accessory=info_tip.render(' in workspace
            or domain == 'alerts' and 'title_accessory=info_tip.render(' in read(ROOT / domain / 'index.html')
        )

    for domain, parts in CONTENT.items():
        for name in parts:
            path = ROOT / domain / 'partials' / name
            source = read(path)
            environment.parse(source)
            assert 'components/info_tip.html' in source, path
            assert 'info_tip.render(' in source, path
            assert "variant='guide'" in source, path


def test_guide_ids_unique_and_forecast_resources_are_scoped_per_tab() -> None:
    paths = set()
    for domain, locations in FOCUS.items():
        for location in locations:
            paths.add(ROOT / domain / location)
    for domain, names in CONTENT.items():
        for name in names:
            paths.add(ROOT / domain / 'partials' / name)

    ids = []
    for path in sorted(paths):
        source = read(path)
        ids.extend(re.findall(r"'(kubernetes-analytics-[A-Za-z0-9_-]+-guide)'", source))

    assert len(ids) == len(set(ids))
    assert len(ids) >= 35
    forecast = read(ROOT / 'forecast/partials/_forecast_section.html')
    assert "'kubernetes-analytics-forecast-resource-' ~ resource_key ~ '-guide'" in forecast
    assert "item.label ~ ' Forecast Guide'" in forecast
    for key in ('cpu', 'memory', 'storage', 'pods', 'trend', 'recommendations'):
        assert f"('{key}'," in forecast


def test_overview_compact_copy_preserves_risk_and_source_semantics() -> None:
    storage = read(ROOT / 'overview/partials/_storage_snapshot.html')
    consumers = read(ROOT / 'overview/partials/_top_consumers_snapshot.html')
    forecast = read(ROOT / 'overview/partials/_forecast_snapshot.html')
    for source in (storage, consumers, forecast):
        Environment(autoescape=True).parse(source)

    assert 'Restore PVC usage evidence before confirming storage health.' in storage
    assert 'Monitor free capacity and Namespace growth; plan expansion before utilization rises.' in storage
    assert 'Storage Evidence Is Limited' in storage
    assert "analysis_surface.unavailable_value_classes()" not in storage
    assert 'Check requests, limits, replicas, and storage allocation before resizing.' in consumers
    assert 'No projected breach in available evidence.' in forecast
    assert 'forecast.risk_note|replace(' in forecast
    assert "tone='warning' if risk_count > 0 else 'normal'" in forecast
    assert 'whitespace-nowrap' not in forecast
    assert 'truncate' not in forecast


def test_focus_guides_do_not_change_lazy_loading_or_filter_ownership() -> None:
    utilization = read(ROOT / 'utilization/index.html')
    workload = read(ROOT / 'workload/index.html')
    storage = read(ROOT / 'storage/partials/_storage_section.html')
    forecast = read(ROOT / 'forecast/partials/_forecast_section.html')
    alerts = read(ROOT / 'alerts/index.html')
    for page in (utilization, workload, storage, forecast, alerts):
        assert 'data-analytics-tab-panel=' in page
        assert 'analytics_workspace.tabbed(' in page

    assert 'kaori:analytics-tab-activated once' in utilization
    assert 'kaori:analytics-tab-activated once' in workload
    assert 'kaori:analytics-tab-activated once' in storage
    assert 'data-analytics-preserve-tab' in alerts
    assert 'resource_tabs[:4]' in forecast
