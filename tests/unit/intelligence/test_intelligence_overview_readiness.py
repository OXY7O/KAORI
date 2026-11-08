from __future__ import annotations

from app.intelligence.overview import _overview_posture, _posture_items


def _inputs():
    return {
        'summary': {'findings': 0, 'critical': 0, 'warning': 0, 'registered_assets': 3},
        'alerts': {
            'critical': 0,
            'warning': 0,
            'source_unknown': 0,
            'verification_pending': 0,
            'postmortem_required': 0,
            'delivery_failures': 0,
            'active': 0,
        },
        'automation': {
            'failures': 0,
            'pending_governance': 0,
            'execution_label': 'Execution Disabled',
        },
    }


def test_empty_findings_with_missing_evidence_is_not_clear() -> None:
    evidence = {'recent': 1, 'total': 3, 'complete': False}
    assert _overview_posture(**_inputs(), evidence=evidence)['label'] == 'Evidence Review Required'
    posture = _posture_items(**_inputs(), evidence=evidence)
    freshness = next(item for item in posture if item['label'] == 'Evidence Freshness')
    assert freshness['tone'] == 'warning'
    assert freshness['value'] == '1 / 3 Recent Inventory'


def test_recent_inventory_with_no_findings_is_not_provider_healthy_claim() -> None:
    posture = _overview_posture(**_inputs(), evidence={'recent': 3, 'total': 3, 'complete': True})
    assert posture['label'] == 'No Active Findings'
    assert posture['tone'] == 'info'
    assert 'not a provider-health claim' in posture['helper']


def test_verification_failed_outcome_forces_control_attention() -> None:
    payload = _inputs()
    payload['automation']['failures'] = 1
    assert (
        _overview_posture(**payload, evidence={'recent': 3, 'total': 3, 'complete': True})['label']
        == 'Control Attention'
    )
