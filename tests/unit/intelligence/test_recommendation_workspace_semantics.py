from __future__ import annotations

from werkzeug.datastructures import MultiDict

from app.intelligence import service
from app.intelligence.recommendation_alerting import matches_alert_handling


def _finding(*, domain: str, severity: str, handling: str = 'not_eligible') -> dict:
    return {
        'domain': domain, 'severity': severity,
        'alert_handling': {'status': handling, 'eligible': handling == 'eligible'},
    }


def test_recommendation_posture_uses_matched_scope_not_unfiltered_critical() -> None:
    payload = {
        'filters': {'domain': 'object_storage', 'provider': ''},
        'active_filter_count': 1,
        'matching_findings': [_finding(domain='object_storage', severity='warning')],
        'evidence_readiness': {'status': 'baseline_recent'},
    }
    service._apply_recommendation_payload(
        payload,
        [
            _finding(domain='kubernetes', severity='critical'),
            _finding(domain='object_storage', severity='warning'),
        ],
    )
    assert payload['summary']['actionable'] == 1
    assert payload['summary']['critical'] == 0
    assert payload['summary']['warning'] == 1
    assert payload['posture']['label'] == 'Review'
    assert payload['scope_label'] == 'Object Storage'


def test_no_findings_does_not_claim_healthy_when_source_incomplete() -> None:
    payload = {
        'filters': {'domain': '', 'provider': ''},
        'active_filter_count': 0,
        'matching_findings': [],
        'evidence_readiness': {'status': 'unavailable'},
    }
    service._apply_recommendation_payload(payload, [])
    assert payload['posture']['label'] == 'Evidence Review Required'
    assert payload['posture']['tone'] == 'warning'


def test_known_non_escalated_case_states_are_filterable() -> None:
    for status in ('source_unknown', 'resolved_pending', 'withdrawn', 'retired', 'resolved'):
        finding = _finding(domain='registry', severity='warning', handling=status)
        assert matches_alert_handling(finding, status, page_mode='recommendations')


def test_hidden_catalog_status_does_not_filter_recommendations(monkeypatch) -> None:
    rows = [{'domain': 'registry', 'severity': 'warning', 'status': 'available'}]
    monkeypatch.setattr(service, 'decorate_catalog_rules', lambda rules: rules)
    monkeypatch.setattr(service, 'decorate_recommendation_findings', lambda findings: findings)
    monkeypatch.setattr(service, 'get_active_recommendation_findings', lambda **kwargs: rows)
    payload = service._base_payload(
        MultiDict([('status', 'reserved'), ('domain', 'registry')]),
        page_mode='recommendations',
    )
    assert payload['filters']['status'] == ''
    assert payload['pagination']['total_items'] == 1
    assert payload['result_context']['registry_items'] == 1
