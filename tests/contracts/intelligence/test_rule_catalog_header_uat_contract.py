from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_catalog_summary_and_definitions_share_canonical_header_labels_and_guide() -> None:
    summary = read('app/templates/intelligence/partials/_catalog_summary.html')
    page = read('app/templates/intelligence/rule_catalog.html')
    count = read('app/templates/intelligence/partials/_catalog_title_count.html')
    for template in (summary, page, count):
        Environment().parse(template)
    assert "table_label.metadata_label('4 Indicators', icon='layout-dashboard')" in summary
    assert 'title_extra=catalog_summary_title_extra' in summary
    assert 'title_extra=catalog_title_extra' in page
    assert 'header_actions=catalog_header_actions' in page
    assert "info_tip.render('rule-catalog-definitions-guide'" in page
    assert "variant='guide'" in page
    assert 'table_label.result_count(payload.pagination.total_items)' in count
    assert 'id="catalog-rule-count"' in count
    assert 'hx-swap-oob="outerHTML"' in count


def test_catalog_header_reset_and_results_only_htmx_sync() -> None:
    actions = read('app/templates/intelligence/partials/_catalog_header_actions.html')
    results = read('app/templates/intelligence/partials/_catalog_results.html')
    for template in (actions, results):
        Environment().parse(template)
    assert 'payload.active_filter_count|default(0) > 0' in actions
    assert 'registry_ui.clear_filters_action(' in actions
    assert "table_ui.action_classes(size='header')" in actions
    assert "target='#catalog-workspace-content'" in actions
    assert "sync='#catalog-workspace-content:replace'" in actions
    assert "swap='outerHTML show:none focus-scroll:false'" in actions
    assert "push_url='true'" in actions
    assert 'id="catalog-header-actions"' in actions
    assert 'hx-swap-oob="outerHTML"' in actions
    assert '_catalog_title_count.html' in results
    assert '_catalog_header_actions.html' in results
    assert 'table_label.result_count(' not in results
    assert 'clear_filters_action(' not in results
    assert 'flex flex-col gap-2 border-b' not in results
    assert '_catalog_records.html' in results
    assert 'intelligence_pagination.render(' in results


def test_rule_row_action_uses_shared_compact_toggle_while_retaining_accessibility() -> None:
    records = read('app/templates/intelligence/partials/_catalog_records.html')
    toggle = read('app/templates/components/details/_expandable_row.html')
    assert 'detail_row.toggle_button(' in records
    assert 'table_action=true' in records
    assert "open_label='View Rule'" in records
    assert "close_label='Hide Rule'" in records
    assert 'data-detail-toggle' in toggle
    assert 'aria-expanded="false"' in toggle
    assert 'table_primitives.action_classes()' in toggle


def test_runtime_notice_reuses_shared_semantic_compact_callout_without_new_page_css() -> None:
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    shared = read('app/templates/components/operational_callout.html')
    assert 'operational_callout.render(payload.registry_runtime_evidence.title' in results
    assert 'compact_content=true' in results
    assert 'compact_content=false' in shared
    assert 'mt-1 text-xs leading-5' in shared
    assert 'sm:flex-row sm:items-start sm:justify-between' in shared
