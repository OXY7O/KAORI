from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_top_consumers_emits_semantic_payload_without_css_classes() -> None:
    rows = read('app/analytics/top_consumers/rows.py')
    domain = read('app/analytics/top_consumers/domain.py')

    assert "'tone': normalized" in rows
    assert "'risk': spec.risk" in rows
    assert "'class': 'bg-" not in rows + domain
    assert "'resource_class'" not in rows + domain
    assert "'icon_class'" not in rows + domain


def test_top_consumers_uses_structured_identity_and_correct_pvc_selector() -> None:
    rows = read('app/analytics/top_consumers/rows.py')
    domain = read('app/analytics/top_consumers/domain.py')

    assert 'def build_compute_identity(' in rows
    assert "'workload_owner': spec.workload_owner" in rows
    assert "title='Highest PVC Utilization'" in domain
    assert "selector='pressure'" in domain
    assert 'split(' not in read('app/templates/analytics/top_consumers/partials/_summary.html')


def test_top_consumers_snapshot_items_use_pressure_and_contribution_fields() -> None:
    source = read('app/analytics/top_consumers/service.py')
    helper = source.split('def build_snapshot_items', 1)[1].split('def relative_percent', 1)[0]

    assert "row.get('pressure_percent')" in helper
    assert "row.get('contribution_percent')" in helper
    assert "row.get('usage_percent')" not in helper
