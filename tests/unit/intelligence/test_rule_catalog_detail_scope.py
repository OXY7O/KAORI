from __future__ import annotations

from app.intelligence import service
from app.intelligence.catalog import INTELLIGENCE_CATALOG


def test_catalog_rule_detail_scopes_evaluation_and_owners(monkeypatch) -> None:
    rule = next(item for item in INTELLIGENCE_CATALOG if item['rule_key'] == 'kubernetes.namespace.missing_quota')
    monkeypatch.setattr(service, 'INTELLIGENCE_CATALOG', [rule])
    monkeypatch.setattr(service, 'decorate_catalog_rules', lambda rules: rules)
    captured: dict[str, object] = {}

    def collect(**kwargs):
        captured['evaluation'] = kwargs.copy()
        return []

    def build_view(key, findings, **kwargs):
        captured['exception'] = (key, findings, kwargs)
        return {'assets': []}

    monkeypatch.setattr(service, 'get_active_recommendation_findings', collect)
    monkeypatch.setattr(service, 'build_rule_exception_view', build_view)
    result = service.get_catalog_rule(str(rule['rule_key']), include_owner_options=True)
    assert result is not None
    assert captured['evaluation']['domain'] == 'kubernetes'
    assert captured['evaluation']['rule_keys'] == {rule['rule_key']}
    assert captured['exception'][2]['include_owner_options'] is True


def test_catalog_rule_detail_fail_closed_when_evaluation_partial(monkeypatch) -> None:
    rule = next(item for item in INTELLIGENCE_CATALOG if item['rule_key'] == 'kubernetes.namespace.missing_quota')
    monkeypatch.setattr(service, 'INTELLIGENCE_CATALOG', [rule])
    monkeypatch.setattr(service, 'decorate_catalog_rules', lambda rules: rules)
    captured: dict[str, object] = {}

    def collect(*, evidence_issues, **kwargs):
        evidence_issues.append('Kubernetes Namespace')
        return []

    def build_view(key, findings, **kwargs):
        captured.update(kwargs)
        return {'assets': []}

    monkeypatch.setattr(service, 'get_active_recommendation_findings', collect)
    monkeypatch.setattr(service, 'build_rule_exception_view', build_view)
    result = service.get_catalog_rule(str(rule['rule_key']), include_owner_options=True)
    assert result is not None
    assert result['rule_exceptions']['evaluation_issues'] == ['Kubernetes Namespace']
    assert captured['include_owner_options'] is False
