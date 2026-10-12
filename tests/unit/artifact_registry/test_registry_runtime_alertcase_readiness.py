from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.intelligence.alert_intelligence import recommendation_source


@pytest.mark.parametrize('status', ('inputs_changed', 'stale', 'refresh_failed', 'not_materialized'))
def test_runtime_recommendation_alert_cases_do_not_resolve_on_unqualified_correlation(monkeypatch, status):
    counter = {'reads': 0}

    def readiness(session):
        counter['reads'] += 1
        return {'status': status}

    monkeypatch.setattr(recommendation_source, 'runtime_correlation_evidence_readiness', readiness)
    monkeypatch.setattr(recommendation_source, 'db', SimpleNamespace(session=object()))
    cached: dict[str, str] = {}
    assert recommendation_source._registry_runtime_source_posture(
        'registry.runtime.tag_only_correlation', readiness_cache=cached
    ) == (False, 'source_unavailable')
    assert recommendation_source._registry_runtime_source_posture(
        'registry.security.critical_runtime_vulnerability', readiness_cache=cached
    ) == (False, 'source_unavailable')
    assert counter['reads'] == 1


def test_registry_governance_does_not_depend_on_runtime_correlation(monkeypatch):
    def unexpected(session):
        raise AssertionError('Governance evidence must not require runtime correlation')

    monkeypatch.setattr(recommendation_source, 'runtime_correlation_evidence_readiness', unexpected)
    assert recommendation_source._registry_runtime_source_posture(
        'registry.governance.public_project_without_immutability'
    ) == (True, '')
