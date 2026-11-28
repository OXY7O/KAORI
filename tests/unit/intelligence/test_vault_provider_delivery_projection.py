"""Vault delivery ledger distinguishes exact audited outcomes from ambiguous claims (#5253)."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.intelligence.alert_intelligence import vault_case_delivery_evidence as evidence
from app.intelligence.alert_intelligence.vault_delivery_journal import CLAIM_KEY, REJECTION_KEY


def _row(*, status: str, rejected: bool):
    now = datetime(2026, 11, 28, tzinfo=UTC)
    return SimpleNamespace(
        domain='secrets_pki',
        asset_type='vault_instance',
        asset_key='23',
        event_key='alert-case:CA-01:firing:scoped-v1',
        channel_id=9,
        status=status,
        attempt_count=1,
        created_at=now,
        sent_at=now if status == 'sent' else None,
        next_retry_at=None,
        payload_json={CLAIM_KEY: {}, REJECTION_KEY: rejected},
    )


@pytest.mark.parametrize(
    ('journal_status', 'outcome', 'rejected', 'expected'),
    [
        ('sent', 'sent', False, 'sent'),
        ('failed', 'rejected', True, 'failed'),
        ('failed', 'unconfirmed', False, 'review required'),
        ('queued', None, False, 'review required'),
        ('failed', None, False, 'review required'),
        ('skipped', None, False, 'review required'),
        ('queued', 'sent', False, None),
        ('failed', 'sent', False, None),
        ('sent', 'rejected', True, None),
        ('failed', 'rejected', False, None),
        ('failed', 'unconfirmed', True, None),
    ],
)
def test_canonical_status_requires_matching_committed_outcome(
    monkeypatch, journal_status, outcome, rejected, expected
):
    case = SimpleNamespace(
        public_id='CA-01',
        asset_key='23',
        evidence_json={'source_binding_id': 5},
    )
    row = _row(status=journal_status, rejected=rejected)
    claim = {
        'case_id': 'CA-01',
        'binding_id': 5,
        'policy_id': 8,
        'channel_id': 9,
        'receipt_ref': 'a' * 64,
        'maker_id': 11,
    }
    monkeypatch.setattr(evidence, 'firing_journal', lambda _case: [row])
    monkeypatch.setattr(evidence, 'audited_claim', lambda _case, _row: claim)
    monkeypatch.setattr(evidence, 'audited_outcome', lambda _case, _row: outcome)
    projected = evidence.read_case_delivery_evidence(case)
    if expected is None:
        assert projected['provider_delivery_qualified'] is False
        assert projected['deliveries'] == []
    else:
        assert projected['provider_delivery_qualified'] is True
        assert projected['deliveries'][0]['status'] == expected
        assert projected['deliveries'][0]['attempt_count'] == 1
        assert 'receipt_ref' not in repr(projected)
        assert 'maker_id' not in repr(projected)


def test_missing_claim_audit_never_qualifies_delivery(monkeypatch):
    case = SimpleNamespace(public_id='CA-01', asset_key='23', evidence_json={'source_binding_id': 5})
    monkeypatch.setattr(evidence, 'firing_journal', lambda _case: [_row(status='sent', rejected=False)])
    monkeypatch.setattr(evidence, 'audited_claim', lambda _case, _row: None)
    assert evidence.read_case_delivery_evidence(case)['provider_delivery_qualified'] is False
