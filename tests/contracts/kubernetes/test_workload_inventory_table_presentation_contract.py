from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/inventory/workloads/partials/_table_content.html'


def test_workload_state_uses_plain_table_text() -> None:
    content = TEMPLATE.read_text()

    assert '{{ workload.state_display }}' in content
    assert 'table_label.status_label(workload.state_display' not in content
    assert 'state_tone' not in content
    assert '{% set state_icon =' not in content
    assert 'text-sm font-semibold leading-5 text-content-primary' in content


def test_workload_identity_type_and_strategy_presentation() -> None:
    content = TEMPLATE.read_text()

    assert 'data-lucide="boxes"' not in content
    assert 'table_ui.namespace_identity(workload.namespace)' in content
    assert '{{ workload.type }}' in content
    assert "table_label.metadata_label(workload.type" not in content
    assert "table_label.status_label(workload.update_strategy or 'Unknown', strategy_tone)" in content
    assert "normalized_strategy" in content
    assert "strategy_tone" in content


def test_workload_namespace_uses_identity_icon_and_operational_values_are_bold() -> None:
    content = TEMPLATE.read_text()

    assert "metadata_label(workload.namespace" not in content
    assert 'table_ui.namespace_identity(workload.namespace)' in content
    assert 'font-semibold leading-5 text-content-primary' in content
    assert 'font-semibold tabular-nums text-content-primary' in content
