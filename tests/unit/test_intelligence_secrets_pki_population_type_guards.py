"""Central Intelligence only uses generation-qualified integer PKI evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.intelligence import secrets_pki_recommendations as recommendations


def _snapshot() -> dict[str, object]:
    return {
        'status': 'ready',
        'observed_stored_certificates': 5,
        'within_validity_window': 4,
        'not_yet_valid': 0,
        'expired': 1,
        'unknown': 0,
        'expires_within_7d': 2,
        'expires_8_to_30d': 1,
        'expires_after_30d': 1,
        'last_observed_at': datetime(2026, 10, 27, tzinfo=UTC),
    }


def _findings(monkeypatch: pytest.MonkeyPatch, snapshot: dict[str, object]) -> list[dict[str, object]]:
    monkeypatch.setattr(recommendations, 'build_stored_pki_validity_posture', lambda: snapshot)
    return recommendations.build_secrets_pki_recommendation_findings(
        {recommendations._RULE_KEY: {'status': 'enabled'}}
    )


def test_ready_qualified_pki_population_keeps_critical_recommendation(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = _findings(monkeypatch, _snapshot())

    assert len(findings) == 1
    assert findings[0]['severity'] == 'critical'
    assert findings[0]['priority'] == 'P1'
    evidence = findings[0]['evidence']
    assert evidence['observed_stored_certificates'] == 5
    assert evidence['expired'] == 1
    assert evidence['trust_verified'] is False


@pytest.mark.parametrize(
    ('field', 'invalid'),
    [
        ('expired', None),
        ('expired', True),
        ('expired', -1),
        ('within_validity_window', '4'),
        ('expires_within_7d', 1.0),
    ],
)
def test_unqualified_pki_counts_never_become_zero_or_a_recommendation(
    monkeypatch: pytest.MonkeyPatch, field: str, invalid: object
) -> None:
    snapshot = _snapshot()
    snapshot[field] = invalid

    assert _findings(monkeypatch, snapshot) == []


def test_inconsistent_committed_population_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _snapshot()
    snapshot['observed_stored_certificates'] = 7

    assert _findings(monkeypatch, snapshot) == []


def test_unknown_or_stale_source_is_not_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _snapshot()
    snapshot['status'] = 'partial'

    assert _findings(monkeypatch, snapshot) == []
