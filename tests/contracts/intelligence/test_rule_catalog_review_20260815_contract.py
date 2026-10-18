from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text()


def test_rule_catalog_uses_two_row_filter_layout_and_standalone_summary_box():
    page = read('app/templates/intelligence/rule_catalog.html')
    workspace = read('app/templates/intelligence/partials/_catalog_workspace.html')
    filters = read('app/templates/intelligence/partials/_filters.html')
    results = read('app/templates/intelligence/partials/_catalog_results.html')
    summary = read('app/templates/intelligence/partials/_catalog_summary.html')

    assert 'catalog-summary-section' in page
    assert page.index('catalog-summary-section') < page.index("'Rule Definitions'")
    assert 'filter_compact_two_rows = true' in workspace
    assert 'filter_include_status = true' in workspace
    assert 'if filter_compact_two_rows|default(false)' in filters
    assert 'Availability' in filters
    assert 'Signal Source' in filters
    assert 'hx-swap-oob="outerHTML"' in results
    assert 'Rule Catalog Summary' in summary
    assert 'layout-dashboard' in summary
    assert 'clear_filters_action' in results
    assert "target='#catalog-workspace-content'" in results
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
    assert (
        "item['table_summary'] = _catalog_table_summary(item.get('catalog_summary') or item.get('summary'), limit=56)"
        in service
    )
    assert 'item.table_summary or item.summary' in records
    assert 'mt-1 truncate text-xs leading-5 text-content-muted' in records
    assert 'line-clamp-2' not in records
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


def test_rule_catalog_hero_is_provider_neutral():
    page = read('app/templates/intelligence/rule_catalog.html')
    hero = read('app/templates/intelligence/partials/_catalog_hero_posture.html')
    assert "include 'intelligence/partials/_catalog_hero_posture.html'" in page
    assert 'Canonical Definitions' in hero
    assert "'Asset Domains', payload.summary.domains" in hero
    assert 'MinIO-Covered Rules' not in hero
    assert 'payload.summary.minio' not in hero


def test_rule_catalog_record_table_uses_shared_geometry_and_retains_inline_details():
    from jinja2 import Environment

    records = read('app/templates/intelligence/partials/_catalog_records.html')
    primitives = read('app/templates/components/table_primitives.html')
    Environment().parse(records)

    assert '{% import "components/table_primitives.html" as table_ui %}' in records
    for macro in (
        'table_classes', 'head_classes', 'header_cell_classes',
        'body_classes', 'row_classes', 'cell_classes',
    ):
        assert f'macro {macro}(' in primitives
    assert "table_ui.table_classes('min-w-[980px] !table-fixed')" in records
    assert 'table_ui.head_classes()' in records
    assert 'table_ui.body_classes()' in records
    assert 'table_ui.row_classes()' in records
    assert records.count('scope="col"') == 5
    assert records.count('table_ui.header_cell_classes()') == 4
    assert records.count('table_ui.header_cell_classes(action=true)') == 1
    assert records.count('table_ui.cell_classes()') == 5
    assert records.count('table_ui.cell_classes(action=true)') == 1
    assert '<caption class="sr-only">' in records
    assert '<table class="w-full min-w-[980px] table-fixed' not in records
    for size in ('32', '18', '20', '12'):
        assert f'w-[{size}%]' in records

    # No modal conversion: one shared toggle plus the adjacent five-column detail row.
    assert 'detail_row.toggle_button(' in records
    assert 'detail_row.detail_row(detail_row_id, detail_target_id, 5)' in records
    assert "class_name='justify-end'" in records
    assert "open_label='View Rule'" in records
    assert "close_label='Hide Rule'" in records
    assert "payload['items']|default([], true)" in records
    assert 'No Rule Definitions Match the Current Filters' in records
    for state in ('available', 'imported_signal', 'Recommendation Only', 'Accepted Risk'):
        assert state in records
