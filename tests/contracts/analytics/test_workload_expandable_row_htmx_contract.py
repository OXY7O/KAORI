from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_record_modals_remain_closed_after_htmx_replacement() -> None:
    component = read('app/templates/kubernetes/analytics/components/_record_detail_modal.html')
    tenant = read('app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html')
    script = read('app/static/js/analytics/controls.js')

    for content in (tenant, mapping):
        assert 'x-data="{ detailOpen: false }"' in content
        assert '@kaori:analytics-collapse-details.window="detailOpen = false"' in content
        assert '@click="detailOpen = true"' in content
        assert 'x-bind:hidden="!expanded"' not in content

    assert 'x-show="detailOpen"' in component
    assert 'x-cloak' in component
    assert '@keydown.escape.window="detailOpen = false"' in component
    assert '@click="detailOpen = false"' in component
    assert 'function stabilizeAnalyticsExpandables(root)' in script
    assert "window.dispatchEvent(new CustomEvent('kaori:analytics-collapse-details'))" in script
    assert 'stabilizeAnalyticsExpandables(root)' in script
