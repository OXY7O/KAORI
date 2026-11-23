from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_registry_correlation_is_separate_from_sql_evaluator_failures() -> None:
    service = read('app/intelligence/service.py')
    assert 'source_gaps: list[str] = []' in service
    assert "source_gaps.append('Registry Runtime: ' + runtime_evidence['title'])" in service
    assert "issues.append('Registry Runtime: ' + runtime_evidence['title'])" not in service
    assert "issues.append('Registry Runtime Readiness')" in service
    assert "'source_gaps': source_gaps" in service
    assert 'source_gaps=source_gaps' in service
    assert 'if recent < total or source_gaps:' in service
    assert 'if issues:' in service
    assert 'db.session.rollback()' in service


def test_recommendation_runtime_advisory_and_unavailable_state_remain_distinct() -> None:
    results = read('app/templates/intelligence/partials/_recommendations_results.html')
    records = read('app/templates/intelligence/partials/_recommendation_records.html')
    reconciler = read('app/intelligence/alert_intelligence/recommendation_source.py')
    assert "payload.registry_runtime_evidence.status != 'ready'" in results
    assert "action_href=url_for('artifact_registry.runtime')" in results
    assert 'A committed evidence evaluation or readiness read failed.' in records
    assert "'source_unavailable'" in reconciler
    assert '_registry_runtime_source_posture' in reconciler
