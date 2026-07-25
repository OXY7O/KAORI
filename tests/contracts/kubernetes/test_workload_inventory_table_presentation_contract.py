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


def test_workload_name_icon_uses_compact_row_scale() -> None:
    content = TEMPLATE.read_text()

    assert 'flex h-7 w-7 shrink-0 items-center justify-center rounded-md' in content
    assert 'data-lucide="boxes" class="h-4 w-4"' in content
    assert 'flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-kaori-soft text-kaori-primary"><i data-lucide="boxes"' not in content
