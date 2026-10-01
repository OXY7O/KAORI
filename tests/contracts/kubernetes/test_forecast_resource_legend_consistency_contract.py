from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_kubernetes_forecast_resource_palette_is_shared_across_overview_surfaces() -> None:
    legend = read('app/templates/components/resource_series_legend.html')
    shared_chart = read('app/templates/components/forecast_projection_chart.html')
    interactive = read('app/templates/kubernetes/analytics/components/_interactive_forecast_chart.html')
    chart_js = read('app/static/js/kubernetes/analytics/forecast_chart.js')
    dashboard = read('app/templates/kubernetes/dashboard/partials/_forecast_risk.html')
    analytics_overview = read('app/templates/kubernetes/analytics/overview/partials/_forecast_snapshot.html')
    analytics_forecast = read('app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html')

    expected = {
        'cpu': ('bg-status-info', 'stroke-status-info', "--kaori-status-info"),
        'memory': ('bg-kaori-primary', 'stroke-kaori-primary', "--kaori-brand-primary"),
        'storage': ('bg-status-normal', 'stroke-status-normal', "--kaori-status-normal"),
        'pods': ('bg-status-warning', 'stroke-status-warning', "--kaori-status-warning"),
    }
    for key, (surface, stroke, css_token) in expected.items():
        assert f"resource_key == '{key}'" in legend
        assert surface in legend
        assert stroke in legend
        assert f"{key}: cssToken('{css_token}'" in chart_js

    assert 'stroke-status-pending' not in shared_chart
    assert 'resource_series_legend.stroke_class(item.key)' in shared_chart
    assert "resource_series_legend.render_series(series, aria_label='Resource Color Legend')" in shared_chart

    assert "resource_series_legend.render_all(aria_label='Resource Forecast Legend')" in interactive
    assert 'resource_series_legend.marker(resource_key, resource_label)' in interactive

    for template in (dashboard, analytics_overview, analytics_forecast):
        assert 'components/resource_series_legend.html' in template
        assert 'resource_series_legend.swatch(item.key)' in template


def test_resource_identity_and_line_semantics_are_separate() -> None:
    shared_chart = read('app/templates/components/forecast_projection_chart.html')
    interactive = read('app/templates/kubernetes/analytics/components/_interactive_forecast_chart.html')

    assert 'aria-label="Resource Color Legend"' in shared_chart
    assert 'aria-label="Forecast Line and Threshold Legend"' in shared_chart
    assert '>Historical</span>' in shared_chart
    assert '>Forecast</span>' in shared_chart
    assert 'Warning 75%' in shared_chart
    assert 'Critical 90%' in shared_chart

    assert "aria_label='Resource Forecast Legend'" in interactive
    assert 'aria-label="Forecast Line and Threshold Legend"' in interactive
    assert '>Historical</span>' in interactive
    assert '>Projection</span>' in interactive
    assert '>Warning</span>' in interactive
    assert '>Critical</span>' in interactive
