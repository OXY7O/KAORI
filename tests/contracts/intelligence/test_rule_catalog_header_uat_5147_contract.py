from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


def test_rule_catalog_summary_and_header_use_existing_kaori_components() -> None:
    page = source('app/templates/intelligence/rule_catalog.html')
    summary = source('app/templates/intelligence/partials/_catalog_summary.html')
    results = source('app/templates/intelligence/partials/_catalog_results.html')
    metadata = source('app/templates/intelligence/partials/_catalog_header_metadata.html')
    actions = source('app/templates/intelligence/partials/_catalog_header_actions.html')
    for template in (page, summary, results, metadata, actions):
        Environment().parse(template)
    assert "metadata_label('4 Indicators', 'layout-dashboard')" in summary
    assert 'title_extra=summary_title_extra' in summary
    assert 'title_extra=catalog_title_extra' in page
    assert 'header_actions=catalog_header_actions' in page
    assert "variant='guide'" in page
    assert 'table_label.result_count(payload.pagination.total_items)' in metadata
    assert 'hx-swap-oob="outerHTML"' in metadata
    assert 'hx-swap-oob="outerHTML"' in actions
    assert 'registry_ui.clear_filters_action(' in actions
    assert "table_ui.action_classes(size='header')" in actions
    assert "target='#catalog-workspace-content'" in actions
    assert "sync='#catalog-workspace-content:replace'" in actions
    assert '_catalog_header_actions.html' in results
    assert '_catalog_header_metadata.html' in results
    assert 'clear_filters_action' not in results
    assert 'bg-surface-card px-4 py-3 sm:flex-row' not in results


def test_rule_catalog_inline_action_and_recommendation_notice_reuse_shared_geometry() -> None:
    records = source('app/templates/intelligence/partials/_catalog_records.html')
    results = source('app/templates/intelligence/partials/_recommendations_results.html')
    callout = source('app/templates/components/operational_callout.html')
    assert 'table_action=true' in records
    assert 'detail_row.toggle_button(' in records
    assert 'compact_message=true' in results
    assert 'compact_message=false' in callout
    assert 'lg:flex-row lg:items-baseline' in callout
    assert 'if not compact_message' in callout
