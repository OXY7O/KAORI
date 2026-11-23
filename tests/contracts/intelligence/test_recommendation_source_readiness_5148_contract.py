"""Source contract: Registry correlation warnings are not generic evaluator SQL failures."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_registry_runtime_correlation_unmaterialized_does_not_mark_all_evaluators_failed() -> None:
    service = source('app/intelligence/service.py')
    runtime = source('app/common/registry_runtime_evidence.py')
    results = source('app/templates/intelligence/partials/_recommendations_results.html')
    records = source('app/templates/intelligence/partials/_recommendation_records.html')
    assert "if runtime_evidence['status'] == 'unavailable':" in service
    assert "issues.append('Registry Runtime: ' + runtime_evidence['title'])" in service
    assert "elif runtime_evidence['status'] != 'ready':" in service
    assert "source_gaps.append('Registry Runtime: ' + runtime_evidence['title'])" in service
    assert "'source_gaps': source_gaps" in service
    assert 'source_gaps=source_gaps' in service
    assert 'if recent < total or source_gaps:' in service
    assert "'status': 'not_materialized'" in runtime
    assert "'status': 'refresh_failed'" in runtime
    assert "'status': 'stale'" in runtime
    assert "payload.registry_runtime_evidence.status != 'ready'" in results
    assert "readiness_status == 'unavailable'" in records
    assert 'A committed evidence evaluation or readiness read failed.' in records


def test_actual_sql_failures_still_fail_closed_and_catalog_has_separate_evaluation_boundaries() -> None:
    service = source('app/intelligence/service.py')
    catalog = source('app/intelligence/catalog.py')
    alerting = source('app/intelligence/recommendation_alerting.py')
    for evaluator in (
        'Kubernetes Workload Governance',
        'Kubernetes Runtime',
        'Tenant Governance',
        'Object Storage',
        'Artifact Registry',
        'Secrets & PKI',
    ):
        assert f"collect('{evaluator}'" in service
    assert 'except SQLAlchemyError:' in service
    assert 'db.session.rollback()' in service
    assert 'evidence_issues.append(label)' in service
    assert "_ALLOWED_STATUSES = {'available', 'reserved', 'imported_signal'}" in catalog
    assert 'def decorate_recommendation_findings(' in alerting
    assert 'def decorate_catalog_rules(' in alerting
    assert "if str(rule.get('status') or '') != 'available':" in alerting
