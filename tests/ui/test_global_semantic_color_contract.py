from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLES = (ROOT / "frontend/styles.css").read_text(encoding="utf-8")
TABLE_LABEL = (ROOT / "app/templates/components/table_label.html").read_text(encoding="utf-8")
STATUS_BADGE = (ROOT / "app/templates/integrations/partials/_status_badge.html").read_text(encoding="utf-8")
PAGE_HERO = (ROOT / "app/templates/components/page_hero.html").read_text(encoding="utf-8")


def test_final_semantic_palette_is_global():
    expected = {
        "--kaori-brand-primary: #7c3aed;",
        "--kaori-brand-primary-dark: #6d28d9;",
        "--kaori-brand-soft: #f5f3ff;",
        "--kaori-status-info: #2563eb;",
        "--kaori-status-info-soft: #eff6ff;",
        "--kaori-status-info-text: #1d4ed8;",
        "--kaori-status-normal: #059669;",
        "--kaori-status-normal-soft: #ecfdf5;",
        "--kaori-status-normal-text: #047857;",
        "--kaori-status-warning: #d97706;",
        "--kaori-status-warning-soft: #fffbeb;",
        "--kaori-status-warning-text: #b45309;",
        "--kaori-status-critical: #dc2626;",
        "--kaori-status-critical-soft: #fef2f2;",
        "--kaori-status-critical-text: #b91c1c;",
        "--kaori-status-unknown: #64748b;",
        "--kaori-status-unknown-soft: #f8fafc;",
        "--kaori-status-unknown-text: #475569;",
    }
    missing = sorted(value for value in expected if value not in STYLES)
    assert not missing, missing


def test_semantic_labels_are_borderless_globally():
    assert ".kaori-semantic-label," in STYLES
    assert ".kaori-context-label," in STYLES
    assert "border-width: 0 !important;" in STYLES
    assert "rounded-md border px-2" not in TABLE_LABEL
    assert "rounded-md border px-2" not in STATUS_BADGE
    assert "kaori-context-label inline-flex min-h-8 w-fit items-center gap-2 rounded-lg border" not in PAGE_HERO
    assert "kaori-context-label inline-flex min-h-8 items-center gap-2 rounded-md border" not in PAGE_HERO


def test_secondary_states_map_to_final_semantic_families():
    assert "tone == 'maintenance' %}bg-status-warning-soft text-status-warning-text" in TABLE_LABEL
    assert "tone == 'pending' %}bg-status-info-soft text-status-info-text" in TABLE_LABEL
    assert "tone == 'disabled' %}bg-status-disabled-soft text-status-disabled-text" in TABLE_LABEL
