from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_workload_inventory_uses_canonical_titles_and_sentence_case() -> None:
    summary = _read('app/templates/inventory/workloads/partials/_summary_cards.html')
    table = _read('app/templates/inventory/workloads/partials/_table_card.html')

    for copy in (
        'Workload Delivery Posture',
        'Controller Workloads',
        'Batch Workloads',
        'Unknown State',
        'Search Workloads',
        'Search workload name',
    ):
        assert copy in summary + table

    assert 'Search Workload</label>' not in table
    assert 'Running Ratio' not in summary
    assert 'Running Coverage' not in summary


def test_workload_pagination_uses_lowercase_preposition() -> None:
    template = _read('app/templates/inventory/workloads/partials/_table_content.html')
    assert '</span> of <span' in template
    assert '</span> Of <span' not in template
    assert "'Workload' if pagination.total_items == 1 else 'Workloads'" in template


def test_delivery_and_placement_is_full_width_factual_evidence() -> None:
    template = _read('app/templates/inventory/workloads/partials/_workload_detail_content.html')
    assert 'Delivery & Placement' in template
    assert 'Delivery Configuration' in template
    assert 'Placement Constraints' in template
    assert 'No Implicit Workload Configuration Scoring' not in template
    assert 'table_label.status_label(container.pull_policy' not in template
