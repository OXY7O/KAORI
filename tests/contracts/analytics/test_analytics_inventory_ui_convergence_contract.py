import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_inherits_inventory_palette_tokens() -> None:
    css = read('frontend/styles.css')
    compiled = read('app/static/css/output.css')

    assert '.kaori-analytics-page {' not in css
    assert '.dark .kaori-analytics-page {' not in css
    assert '.kaori-analytics-page{' not in compiled
    assert '.dark .kaori-analytics-page{' not in compiled
    assert 'Analytics pages inherit the same KAORI surface' in css


def test_shared_analytics_surfaces_delegate_to_inventory_components() -> None:
    surfaces = read('app/templates/analytics/components/_analysis_surfaces.html')
    workspace = read('app/templates/analytics/kubernetes/components/_analysis_workspace.html')
    table = read('app/templates/components/table.html')
    primitives = read('app/templates/components/table_primitives.html')

    assert 'components/table_primitives.html' in table
    assert 'macro block_classes' in primitives
    assert 'macro filter_label_classes' in primitives
    assert 'macro title_cell' in primitives

    assert 'components/table_primitives.html' in surfaces
    assert 'table_ui.block_classes()' in surfaces
    assert 'table_ui.block_header_classes()' in surfaces
    assert 'table_ui.block_icon_classes()' in surfaces
    assert 'components/table_primitives.html' in workspace
    assert 'table_ui.filter_label_classes()' in workspace
    assert 'table_ui.filter_select_classes()' in workspace


def test_analytics_record_collections_use_inventory_table_grammar() -> None:
    records = read('app/templates/analytics/kubernetes/components/_evidence_record_list.html')
    filters = read('app/templates/analytics/kubernetes/components/_record_filter_bar.html')

    assert 'table_ui.block_classes()' in records
    assert 'table_ui.title_cell(title, subtitle, icon)' in records
    assert 'bg-surface-hover' in records
    assert 'hover:bg-kaori-mist' in records
    assert 'table_ui.filter_label_classes()' in filters
    assert 'table_ui.filter_input_classes()' not in filters  # search_field owns it
    assert 'table_ui.search_field' in filters
    assert 'table_ui.filter_select_classes()' in filters
    assert 'bg-surface-hover' in filters


def test_inventory_and_analytics_share_pagination_footer_contract() -> None:
    pagination = read('app/templates/components/pagination.html')
    analytics = read('app/templates/analytics/kubernetes/components/_record_pagination.html')
    payloads = read('app/analytics/kubernetes/common/payloads.py')

    assert "'per_page': 5" in payloads
    assert "'per_page': 10" not in payloads

    for token in (
        'footer_classes',
        'summary_group_classes',
        'rows_group_classes',
        'navigation_group_classes',
        'resource_name',
    ):
        assert f'macro {token}' in pagination

    assert 'pagination_ui.footer_classes()' in analytics
    assert 'pagination_ui.resource_name(resource_label, total_rows)' in analytics
    assert 'Showing <span class="font-semibold text-content-primary">{{ start_item }}</span>–' in analytics
    assert '>Rows</label>' in analytics
    assert 'allowed_per_page=(5, 10, 25, 50)' in analytics
    assert 'Scope Contains' not in analytics

    inventory_tables = list((ROOT / 'app/templates/inventory/kubernetes').glob('*/partials/_table_content.html'))
    assert len(inventory_tables) >= 8
    for template in inventory_tables:
        source = template.read_text(encoding='utf-8')
        assert 'pagination_ui.footer_classes()' in source
        assert 'pagination_ui.summary_group_classes()' in source
        assert 'pagination_ui.navigation_group_classes()' in source
        assert 'pagination_ui.resource_name(' in source


def test_analytics_filter_labels_are_explicitly_associated() -> None:
    violations: list[str] = []
    for template in (ROOT / 'app/templates/analytics').rglob('*.html'):
        source = template.read_text(encoding='utf-8')
        for line_number, line in enumerate(source.splitlines(), start=1):
            if '<label class=' in line and 'for=' not in line:
                violations.append(f'{template.relative_to(ROOT)}:{line_number}')
    assert violations == []


def test_capacity_review_path_uses_shared_row_pattern() -> None:
    surfaces = read('app/templates/analytics/components/_analysis_surfaces.html')
    risk = read('app/templates/analytics/kubernetes/capacity/partials/_risk.html')

    assert 'macro review_path_link' in surfaces
    assert 'hover:bg-kaori-mist' in surfaces
    assert 'analysis_surface.review_path_link(' in risk
    assert "' Finding' if finding_count == 1 else ' Findings'" in risk
    assert 'rounded-lg border border-outline-subtle bg-surface-card px-4 py-3 transition' not in risk


def test_showing_and_rows_copy_has_one_analytics_owner() -> None:
    owners: list[str] = []
    for template in (ROOT / 'app/templates/analytics').rglob('*.html'):
        source = template.read_text(encoding='utf-8')
        if re.search(r'\bShowing\s+<', source) or 'Rows Per Page' in source:
            owners.append(str(template.relative_to(ROOT)))
    assert owners == ['app/templates/analytics/kubernetes/components/_record_pagination.html']
