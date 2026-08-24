from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def inventory_templates() -> str:
    base = ROOT / 'app/templates/storage/object_storage/inventory'
    return '\n'.join(path.read_text(encoding='utf-8') for path in sorted(base.rglob('*.html')))


def test_object_storage_requested_wording_is_concise_and_locked() -> None:
    system_presentation = read('app/storage/object_storage/inventory/system_presentation.py')
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    summary = read('app/templates/storage/object_storage/inventory/buckets/partials/_summary_cards.html')
    detail = read('app/templates/storage/object_storage/inventory/buckets/partials/_bucket_detail_content.html')

    assert 'Committed inventory is available; snapshot or provider conditions need review.' in system_presentation
    assert 'Used size and object count are optional usage evidence.' in presentation
    assert 'Latest committed inventory observation.' in summary
    assert (
        'Usage is collected separately from quota. Prefer provider_metrics; '
        'use full_scan only for exact object enumeration.'
    ) in detail

    old_copy = (
        'Committed inventory is available, with snapshot or provider conditions requiring review.',
        'Used size and current object count are optional inventory evidence collected by the configured usage strategy.',
        'Most recent committed inventory observation in scope.',
        'Usage collection is independent from quota collection.',
    )
    combined = '\n'.join((system_presentation, presentation, summary, detail))
    for wording in old_copy:
        assert wording not in combined


def test_system_id_reuses_shared_accessible_copy_interaction() -> None:
    detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
    shared_detail = read('app/templates/components/details/_detail_content.html')
    clipboard = read('app/static/js/clipboard.js')
    app_layout = read('app/templates/layouts/app.html')

    assert (
        "detail.inventory_technical_row('System ID', system.id, nowrap=true, class_name='lg:col-span-2', copyable=true)"
    ) in detail
    assert 'data-kaori-copy-button' in shared_detail
    assert 'aria-label="Copy {{ label }}"' in shared_detail
    assert 'data-kaori-copy-label aria-live="polite"' in shared_detail
    assert 'data-kaori-copy-source' in shared_detail
    assert "filename='js/clipboard.js'" in app_layout
    assert 'navigator.clipboard?.writeText' in clipboard
    assert "document.execCommand('copy')" in clipboard
    assert 'data-kaori-copy-button' not in detail


def test_inventory_heroes_follow_copy_budget_and_shared_hero_contract() -> None:
    overview = read('app/templates/storage/object_storage/inventory/overview/partials/_hero.html')
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_hero.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_hero.html')

    expected = 'Review committed fleet posture across managed systems and inventory assets.'
    assert expected in overview
    assert len(expected.rstrip('.').split()) <= 16

    for hero in (overview, systems, buckets):
        assert '{% import "components/page_hero.html" as page_hero %}' in hero
        assert 'page_hero.shell_classes()' in hero
        assert 'page_hero.title_classes()' in hero
        assert 'page_hero.description_classes()' in hero
        assert hero.count('<h1') == 1


def test_system_posture_counts_all_provider_attention_without_downgrading_blocked_state() -> None:
    presentation = read('app/storage/object_storage/inventory/presentation.py')
    hero = read('app/templates/storage/object_storage/inventory/systems/partials/_hero.html')

    assert (
        "'attention_systems': sum(1 for row in rows if row['status_tone'] in {'critical', 'warning', 'unknown'})"
    ) in presentation
    assert "'Blocked' if inventory.blocked_systems" in hero
    assert "'critical' if inventory.blocked_systems" in hero
    assert "'Attention Required' if inventory.attention_systems" in hero
    assert "'warning' if inventory.attention_systems" in hero
    assert "'Attention', inventory.attention_systems, 'Systems needing review'" in hero


def test_object_storage_inventory_has_no_page_local_palette_or_typography_drift() -> None:
    source = inventory_templates()

    forbidden_patterns = (
        r'\b(?:bg|text|border|ring)-(?:violet|purple|indigo|blue|green|red|amber|yellow|gray|slate|zinc|neutral)-\d{2,3}\b',
        r'#[0-9A-Fa-f]{6}\b',
        r'\btext-\[[^]]+\]',
        r'\btracking-\[[^]]+\]',
        r'\bfont-(?:bold|extrabold|black)\b',
    )
    for pattern in forbidden_patterns:
        assert re.search(pattern, source) is None

    assert 'components/table.html' in source
    assert 'components/table_label.html' in source
    assert 'components/operational_section_card.html' in source
    assert 'data-kaori-inventory-detail="v10"' in source


def test_inventory_tables_keep_canonical_scope_refresh_and_pagination_ownership() -> None:
    systems = read('app/templates/storage/object_storage/inventory/systems/partials/_table_card.html')
    system_rows = read('app/templates/storage/object_storage/inventory/systems/partials/_table_content.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_card.html')
    bucket_rows = read('app/templates/storage/object_storage/inventory/buckets/partials/_table_content.html')
    presentation = read('app/storage/object_storage/inventory/presentation.py')

    for table in (systems, buckets):
        assert 'hx-swap="outerHTML"' in table
        assert 'partial_mode" value="page_workspace"' in table
        assert 'table_ui.inventory_block_header(' in table

    for rows in (system_rows, bucket_rows):
        assert 'hx-swap="innerHTML"' in rows
        assert 'name="per_page"' in rows
        assert 'allowed_per_page' in rows
        assert 'components/states/_empty_state.html' in rows

    assert presentation.count('per_page: int = 5') >= 2
