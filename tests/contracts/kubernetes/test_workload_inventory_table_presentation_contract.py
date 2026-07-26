from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/inventory/workloads/partials/_table_content.html'


def test_workload_state_uses_plain_table_text() -> None:
    content = TEMPLATE.read_text()

    assert '{{ workload.state_display }}' in content
    assert 'table_label.status_label(workload.state_display' not in content
    assert 'state_tone' not in content
    assert '{% set state_icon =' not in content
    assert 'text-sm font-medium leading-5 text-content-secondary' in content


def test_workload_identity_type_and_strategy_use_plain_table_text() -> None:
    content = TEMPLATE.read_text()

    assert 'data-lucide="boxes"' not in content
    assert 'flex h-7 w-7 shrink-0 items-center justify-center rounded-md' not in content
    assert '{{ workload.type }}' in content
    assert '{{ workload.update_strategy }}' in content
    assert "table_label.metadata_label(workload.type" not in content
    assert "table_label.status_label(workload.update_strategy" not in content


def test_workload_namespace_name_and_pod_count_are_plain_text() -> None:
    content = TEMPLATE.read_text()

    assert "metadata_label(workload.namespace" not in content
    assert 'font-semibold leading-5 text-content-primary' not in content
    assert 'font-semibold tabular-nums text-content-primary' not in content
