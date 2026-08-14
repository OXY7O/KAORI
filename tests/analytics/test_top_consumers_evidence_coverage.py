from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_multi_resource_coverage_has_complete_partial_and_unavailable_states() -> None:
    domain = read('app/analytics/kubernetes/top_consumers/domain.py')

    assert "evidence_state('unavailable')" in domain
    assert "evidence_state('complete' if complete else 'partial')" in domain
    assert "'unavailable_count': unavailable_count" in domain


def test_page_posture_does_not_mark_incomplete_evidence_healthy() -> None:
    domain = read('app/analytics/kubernetes/top_consumers/domain.py')

    assert 'elif incomplete:' in domain
    assert "'label': 'Limited Evidence'" in domain
    assert "'label': 'Healthy'" in domain
