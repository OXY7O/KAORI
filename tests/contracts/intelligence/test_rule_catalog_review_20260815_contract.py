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
    assert 'Rule Catalog Summary' in summary
    assert 'Matching Rules' in summary
    assert 'Reserved Plan' in summary
    assert 'Imported Signal' in summary


def test_rule_catalog_rows_use_short_summary_and_detail_view_remains_full():
    service = read('app/intelligence/service.py')
    records = read('app/templates/intelligence/partials/_catalog_records.html')
    details = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    assert "item['table_summary'] = _truncate_words(item.get('summary'))" in service
    assert 'item.table_summary or item.summary' in records
    assert 'Condition' in details
    assert 'Operational Impact' in details
    assert 'Signal Boundary' in details
    assert 'Recommended Action' in details
