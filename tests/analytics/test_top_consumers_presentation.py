from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_top_consumers_service_emits_semantic_payload_without_css_classes() -> None:
    source = read('app/analytics/top_consumers/service.py')

    assert "'tone': normalized" in source
    assert "'risk': risk" in source
    assert "'class': 'bg-" not in source
    assert "'resource_class'" not in source
    assert "'icon_class'" not in source


def test_top_consumers_uses_structured_identity_and_correct_pvc_selector() -> None:
    source = read('app/analytics/top_consumers/service.py')

    assert 'def build_compute_identity(' in source
    assert "'workload_owner': workload_owner" in source
    assert "title='Highest PVC Utilization'" in source
    assert "selector='pressure'" in source
    assert 'split(' not in read('app/templates/analytics/top_consumers/partials/_summary.html')


def test_top_consumers_snapshot_items_use_new_pressure_and_contribution_fields() -> None:
    source = read('app/analytics/top_consumers/service.py')
    helper = source.split('def _build_top_consumer_items', 1)[1].split('def _raw_percent', 1)[0]

    assert "row.get('pressure_percent')" in helper
    assert "row.get('contribution_percent')" in helper
    assert "row.get(\n                'usage_percent'" not in helper
