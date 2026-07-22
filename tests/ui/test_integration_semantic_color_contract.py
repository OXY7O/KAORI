from pathlib import Path

STYLES = Path('frontend/styles.css')
TABLE_LABEL = Path('app/templates/components/table_label.html')
PAGE_HERO = Path('app/templates/components/page_hero.html')
STATUS_BADGE = Path('app/templates/integrations/partials/_status_badge.html')


def test_final_semantic_palette_is_global() -> None:
    source = STYLES.read_text(encoding='utf-8').lower()
    expected = (
        '--kaori-brand-primary: #7c3aed;',
        '--kaori-brand-primary-hover: #6d28d9;',
        '--kaori-brand-soft: #f5f3ff;',
        '--kaori-brand-border: #c4b5fd;',
        '--kaori-status-info: #2563eb;',
        '--kaori-status-info-text: #1d4ed8;',
        '--kaori-status-info-soft: #eff6ff;',
        '--kaori-status-info-border: #bfdbfe;',
        '--kaori-status-normal: #059669;',
        '--kaori-status-normal-text: #047857;',
        '--kaori-status-normal-soft: #ecfdf5;',
        '--kaori-status-normal-border: #a7f3d0;',
        '--kaori-status-warning: #d97706;',
        '--kaori-status-warning-text: #b45309;',
        '--kaori-status-warning-soft: #fffbeb;',
        '--kaori-status-warning-border: #fde68a;',
        '--kaori-status-critical: #dc2626;',
        '--kaori-status-critical-text: #b91c1c;',
        '--kaori-status-critical-soft: #fef2f2;',
        '--kaori-status-critical-border: #fecaca;',
        '--kaori-status-unknown: #64748b;',
        '--kaori-status-unknown-text: #475569;',
        '--kaori-status-unknown-soft: #f8fafc;',
        '--kaori-status-unknown-border: #cbd5e1;',
    )
    missing = [item for item in expected if item not in source]
    assert not missing, f'Final KAORI semantic colors are missing: {missing}'


def test_labels_are_borderless_globally() -> None:
    styles = STYLES.read_text(encoding='utf-8')
    table_label = TABLE_LABEL.read_text(encoding='utf-8')
    hero = PAGE_HERO.read_text(encoding='utf-8')
    badge = STATUS_BADGE.read_text(encoding='utf-8')

    assert '.kaori-semantic-label,' in styles
    assert '.kaori-context-label,' in styles
    assert 'border-width: 0 !important;' in styles
    assert 'rounded-md border px-2' not in table_label
    assert 'rounded-md border px-2' not in badge
    assert 'kaori-semantic-label' in table_label
    assert 'kaori-semantic-label' in badge
    assert hero.count('kaori-context-label') >= 2
    assert 'kaori-context-label inline-flex min-h-8 w-fit items-center gap-2 rounded-lg border' not in hero


def test_secondary_states_use_six_family_contract() -> None:
    table_label = TABLE_LABEL.read_text(encoding='utf-8')
    assert "tone == 'maintenance' %}bg-status-warning-soft text-status-warning-text" in table_label
    assert "tone == 'pending' %}bg-status-info-soft text-status-info-text" in table_label
    assert "tone == 'disabled' %}bg-status-disabled-soft text-status-disabled-text" in table_label
