from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_compute_policy_matches_workload_request_and_limit_contract() -> None:
    rows = read('app/analytics/top_consumers/rows.py')

    assert "return semantic_state('critical', 'Request Missing')" in rows
    assert "return semantic_state('warning', 'Memory Limit Missing')" in rows
    assert "return semantic_state('info', 'CPU Limit Unset')" in rows
    assert 'for value in (request_utilization, limit_utilization)' in rows


def test_top_consumers_does_not_compare_heterogeneous_absolute_values() -> None:
    presentation = read('app/analytics/top_consumers/presentation.py')

    assert "if selected_sort == 'absolute' and selected_resource != 'all'" in presentation
    assert "if selected_sort == 'contribution'" in presentation
    assert "if selected_sort == 'resource'" in presentation
