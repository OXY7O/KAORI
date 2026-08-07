from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "app/templates/integrations/kubernetes/partials/_inventory_lifecycle.html"


def source() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_inventory_lifecycle_uses_connected_snapshot_and_side_decision_panel():
    text = source()
    assert 'data-kaori-inventory-lifecycle-v4' in text
    assert 'data-kaori-inventory-snapshot-strip' in text
    assert 'data-kaori-inventory-decision' in text
    assert 'xl:grid-cols-[minmax(0,1fr)_28rem]' in text
    assert '2xl:grid-cols-[minmax(0,1fr)_30rem]' in text
    assert 'max-w-[64%]' in text
    assert 'Connection Lifecycle' in text


def test_inventory_lifecycle_keeps_kaori_table_standard_for_bound_sources():
    text = source()
    assert 'table_ui.table_classes' in text
    assert 'table_ui.head_classes()' in text
    assert 'table_ui.row_classes()' in text
    assert "display='indicator'" in text


def test_inventory_lifecycle_uses_violet_for_identity_not_full_surfaces():
    text = source()
    assert 'bg-kaori-soft text-kaori-primary' in text
    assert 'data-kaori-violet-command-strip' not in text
    assert 'bg-kaori-soft p-5 sm:p-6' not in text


def test_inventory_lifecycle_consolidates_retention_and_delete_boundary():
    text = source()
    assert 'Retention Boundary' in text
    assert 'Lifecycle Impact' in text
    assert 'Guardrails Passed' in text
    assert 'Delete Connection' in text
    assert 'data-kaori-connection-lifecycle' not in text
