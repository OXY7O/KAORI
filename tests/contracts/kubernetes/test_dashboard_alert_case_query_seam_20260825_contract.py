from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_cluster_health_uses_patchable_alert_case_loader_boundary() -> None:
    service = read('app/kubernetes/dashboard/service.py')
    assert 'def _alert_cases_by_asset(' in service
    assert 'return active_recommendation_alert_cases_by_asset(' in service
    cluster_health = service.split("if section == 'cluster_health':", 1)[1].split("if section == 'kpis':", 1)[0]
    assert '_alert_cases_by_asset(visible_cluster_ids)' in cluster_health
    assert 'active_recommendation_alert_cases_by_asset(' not in cluster_health
