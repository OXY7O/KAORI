from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_multi_resource_coverage_has_complete_partial_and_unavailable_states() -> None:
    source = read('app/analytics/top_consumers/service.py')

    assert "state = evidence_state('unavailable')" in source
    assert "state = evidence_state('complete')" in source
    assert "state = evidence_state('partial')" in source
    assert "'unavailable_count': unavailable_count" in source


def test_page_posture_does_not_mark_incomplete_evidence_healthy() -> None:
    source = read('app/analytics/top_consumers/service.py')

    assert "elif incomplete:" in source
    assert "'label': 'Evidence Incomplete'" in source
    assert "'label': 'Healthy'" in source
