from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_rule_catalog_uses_two_row_filter_layout_and_summary_box():
    workspace = read('app/templates/intelligence/partials/_catalog_workspace.html')
    filters = read('app/templates/intelligence/partials/_filters.html')
    results = read('app/templates/intelligence/partials/_catalog_results.html')
    summary = read('app/templates/intelligence/partials/_catalog_summary.html')

    assert 'filter_compact_two_rows = true' in workspace
    assert 'if filter_compact_two_rows|default(false)' in filters
    assert 'Signal Source' in filters
    assert "_catalog_summary.html" in results
    assert 'Rule Definitions' in results
    assert 'Rule Catalog Summary' in summary
    assert 'Matching Rules' in summary
    assert 'Reserved Plan' in summary
    assert 'Imported Signal' in summary


def test_rule_catalog_rows_use_short_summary_and_standard_detail_toggle():
    service = read('app/intelligence/service.py')
    records = read('app/templates/intelligence/partials/_catalog_records.html')

    assert 'def _truncate_words(' in service
    assert 'def _count_active_filters(' in service
    assert service.index('def _truncate_words(') < service.index('def _base_payload(')
    assert service.index('def _count_active_filters(') < service.index('def _base_payload(')
    assert "item['table_summary'] = _truncate_words(item.get('summary'))" in service
    assert 'item.table_summary or item.summary' in records
    assert 'components/details/_expandable_row.html' in records
    assert 'detail_row.toggle_button(' in records


def test_rule_catalog_detail_uses_stacked_evaluation_logic_not_three_cards():
    details = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    assert 'Evaluation Logic' in details
    assert 'Condition' in details
    assert 'Operational Impact' in details
    assert 'Signal Boundary' in details
    assert 'Recommended Action' in details
    assert 'overflow-hidden rounded-lg border border-outline-subtle bg-surface-hover' in details
    assert details.count('<article class="rounded-lg border border-outline-subtle bg-surface-hover p-4">') == 0
