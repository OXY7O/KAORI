"""Recommendations record readability and shared KAORI table contract."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
RECORDS = ROOT / 'app/templates/intelligence/partials/_recommendation_records.html'


def read() -> str:
    return RECORDS.read_text(encoding='utf-8')


def test_recommendation_records_keep_canonical_table_and_modal_semantics() -> None:
    source = read()
    Environment().parse(source)
    assert 'components/table.html' in source
    assert 'components/table_label.html' in source
    assert 'components/resource_detail_modal.html' in source
    assert 'table_ui.head_classes()' in source
    assert 'table_ui.body_classes()' in source
    assert 'table_ui.row_classes()' in source
    assert 'table_ui.cell_classes()' in source
    assert 'table_ui.cell_classes(true)' in source
    assert '<caption class="sr-only">' in source
    assert source.count('scope="col"') == 6
    assert 'resource_detail_modal.detail_button(item.rule_key' in source
    assert 'data-detail-toggle' not in source


def test_desktop_records_use_six_balanced_content_groups() -> None:
    source = read()
    desktop = source.split('<div class="grid gap-3 p-4 lg:hidden">', 1)[0]
    assert desktop.count('min-h-24') == 6
    assert desktop.count('table_ui.cell_classes()') == 5
    assert desktop.count('table_ui.cell_classes(true)') == 1
    for width in ('29', '22', '17', '15', '8', '9'):
        assert f'<col class="w-[{width}%]">' in desktop
    assert 'items-center justify-end' in desktop
    assert 'flex-col items-start justify-center' in desktop
    assert 'table_label.status_label(item.severity_label, item.tone' in desktop


def test_long_titles_scopes_and_evidence_keep_full_hover_text() -> None:
    source = read()
    desktop = source.split('<div class="grid gap-3 p-4 lg:hidden">', 1)[0]
    assert 'line-clamp-2 break-words text-sm font-semibold' in desktop
    assert 'title="{{ item.title }}"' in source
    assert 'title="{{ item.scope_title|default(\'Asset Scope\', true) }}"' in source
    assert 'title="{{ item.signal_source_label }}"' in desktop
    assert "item.scope_title|default('Asset Scope', true)" in source
    assert 'item.scope_supporting|default(item.source_kind_label, true)' in source
    assert 'item.list_scope_title|default(item.scope_title|' in source
    assert 'item.list_summary|default(item.summary, true)' in source
    assert 'line-clamp-1' in desktop
    assert '[overflow-wrap:anywhere]' in desktop


def test_evidence_and_alert_handling_stay_source_authoritative() -> None:
    source = read()
    desktop = source.split('<div class="grid gap-3 p-4 lg:hidden">', 1)[0]
    for field in (
        'item.signal_source_label',
        'item.logic_type_label',
        'item.evidence.provider_label',
        'item.alert_handling.label',
        'item.alert_handling.tone',
        'item.severity_label',
        'item.tone',
    ):
        assert field in desktop
    assert "table_label.metadata_label(item.logic_type_label, 'list-checks')" in desktop
    evidence_cell = desktop.split('title="{{ item.signal_source_label }}', 1)[1].split(
        '<td class="{{ table_ui.cell_classes() }}">', 1
    )[0]
    assert evidence_cell.count('table_label.metadata_label(') == 1
    assert "table_label.metadata_label(item.logic_type_label, 'list-checks')" in evidence_cell
    assert 'item.evidence.provider_label' in evidence_cell
    assert "table_label.metadata_label(item.evidence.provider_label, 'database')" not in evidence_cell
    assert '<p class="mt-1 text-xs leading-5 text-content-muted">{{ item.logic_type_label }}</p>' not in desktop
    for state in (
        'escalated',
        'exception_active',
        'source_unknown',
        'resolved_pending',
        'withdrawn',
        'retired',
        'resolved',
    ):
        assert f"item.alert_handling.status == '{state}'" in desktop
    assert 'item.alert_handling.eligible' in desktop
    assert 'No alert lifecycle' in desktop
    assert 'line-clamp-2 break-words text-xs leading-5 text-content-muted' in desktop


def test_mobile_cards_and_empty_states_remain_intact() -> None:
    source = read()
    assert 'class="grid gap-3 p-4 lg:hidden"' in source
    assert 'line-clamp-2 break-words text-sm font-semibold' in source
    assert 'title="{{ item.scope_title|default(\'Asset Scope\', true) }}"' in source
    assert 'sm:grid-cols-2' in source
    assert 'resource_detail_modal.detail_button(item.rule_key' in source
    for state in ('unavailable', 'not_collected', 'partial'):
        assert f"'{state}'" in source
    assert 'No Matching Findings' in source
    assert 'No Active Findings' in source
