"""Local delivery controls do not authorize transport (#5253)."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from werkzeug.exceptions import BadRequest

from app.intelligence.alert_intelligence import vault_case_delivery_evidence as evidence
from app.intelligence.alert_intelligence.vault_delivery_web import _candidate_pair


@pytest.mark.parametrize('value', ['', '1', '1:2:3', '0:2', '01:2', '1:-1', '1:2147483648'])
def test_candidate_pair_rejects_malformed_input(value):
    with pytest.raises(BadRequest):
        _candidate_pair(value)


def test_candidate_pair_preserves_exact_displayed_pair():
    assert _candidate_pair('11:23') == (11, 23)


@pytest.mark.parametrize('prior_claim', [False, True])
def test_absent_journal_does_not_erase_prior_claim(monkeypatch, prior_claim):
    case = SimpleNamespace(public_id='CA-01')
    monkeypatch.setattr(evidence, 'firing_journal', lambda _case: [])
    monkeypatch.setattr(evidence, 'claim_exists', lambda _case: prior_claim)
    result = evidence.read_case_delivery_evidence(case)
    assert result['provider_delivery_qualified'] is False
    assert result['provider_delivery_state'] == ('unavailable' if prior_claim else 'no_claim')
    assert result['provider_retry_due'] is False


def test_rejected_claim_needs_due_time_and_attempt_budget(monkeypatch):
    now = datetime.now(UTC)
    case = SimpleNamespace(public_id='CA-01')
    row = SimpleNamespace(attempt_count=2, next_retry_at=now, created_at=now, sent_at=None)
    monkeypatch.setattr(evidence, 'firing_journal', lambda _case: [row])
    monkeypatch.setattr(evidence, 'audited_claim', lambda _case, _row: {})
    monkeypatch.setattr(evidence, '_qualified', lambda *_args: True)
    monkeypatch.setattr(evidence, 'audited_outcome', lambda *_args: 'rejected')
    monkeypatch.setattr(evidence, '_qualified_delivery_status', lambda *_args: 'failed')
    monkeypatch.setattr(evidence, 'notification_delivery_max_attempts', lambda: 3)
    result = evidence.read_case_delivery_evidence(case)
    assert result['provider_delivery_state'] == 'rejected'
    assert result['provider_retry_due'] is True
    monkeypatch.setattr(evidence, 'notification_delivery_max_attempts', lambda: 2)
    assert evidence.read_case_delivery_evidence(case)['provider_retry_due'] is False
