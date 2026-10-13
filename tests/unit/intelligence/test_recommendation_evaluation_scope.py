from __future__ import annotations

from app.intelligence import recommendation_alerting, service
from app.intelligence.catalog import INTELLIGENCE_CATALOG


def test_missing_prefetched_override_does_not_fall_back_to_per_finding_db(monkeypatch) -> None:
    rule_key = str(INTELLIGENCE_CATALOG[0]['rule_key'])

    class QueryMustNotRun:
        def filter_by(self, **_kwargs):
            raise AssertionError('missing policy override must not issue a SQL query')

    monkeypatch.setattr(recommendation_alerting.RecommendationAlertPolicy, 'query', QueryMustNotRun())
    policy = recommendation_alerting.effective_alert_policy(rule_key, override_loaded=True)
    assert policy['source'] == 'definition'


def test_registry_catalog_scope_does_not_evaluate_unrelated_domain(monkeypatch) -> None:
    def unrelated(_rules):
        raise AssertionError('Kubernetes or Object Storage should not be evaluated for Registry')

    monkeypatch.setattr(service, '_build_namespace_quota_findings', unrelated)
    monkeypatch.setattr(service, 'build_object_storage_recommendation_findings', unrelated)
    monkeypatch.setattr(service, 'build_registry_recommendation_findings', lambda _rules: [])
    rules = [service.normalize_rule(dict(rule)) for rule in INTELLIGENCE_CATALOG if rule['domain'] == 'registry']
    assert service._build_recommendation_findings(rules) == []


def test_detail_lookup_requests_only_its_base_rule(monkeypatch) -> None:
    calls = []

    def evaluate(**kwargs):
        calls.append(kwargs)
        return [{'rule_key': 'registry.security.scan_evidence_missing:42', 'title': 'Scan evidence missing'}]

    monkeypatch.setattr(service, 'get_active_recommendation_findings', evaluate)
    monkeypatch.setattr(service, 'decorate_recommendation_findings', lambda findings: findings)
    finding = service.get_recommendation_finding('registry.security.scan_evidence_missing:42')
    assert finding is not None
    assert calls == [{'rule_keys': {'registry.security.scan_evidence_missing'}}]
