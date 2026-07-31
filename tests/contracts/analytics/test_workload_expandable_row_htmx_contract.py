from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_expandable_rows_remain_closed_after_htmx_replacement() -> None:
    tenant = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')
    script = read('app/static/js/analytics_controls.js')

    for content in (tenant, mapping):
        assert '@kaori:analytics-collapse-details.window="expanded = false"' in content
        assert 'x-bind:hidden="!expanded"' in content
        assert '\n                             hidden\n                             x-cloak' in content

    assert 'function stabilizeAnalyticsExpandables(root)' in script
    assert "window.dispatchEvent(new CustomEvent('kaori:analytics-collapse-details'))" in script
    assert 'stabilizeAnalyticsExpandables(root)' in script
