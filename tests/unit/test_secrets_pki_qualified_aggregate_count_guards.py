"""Validated committed Vault aggregates never treat unknown counts as qualified."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.intelligence import secrets_pki_recommendations as recommendations
from app.secrets_pki import binding_coverage

_OBSERVED = datetime(2026, 10, 27, tzinfo=UTC)


def _qualified_sample(value: object = 2, *, key: str = 'observed_rows') -> tuple[object, ...]:
    counts: dict[str, object] = {
        'observed_rows': 2,
        'firing': 1,
        'suppressed': 1,
        'unprocessed': 0,
        'critical': 1,
        'warning': 1,
        'info': 0,
    }
    counts[key] = value
    return (
        '7',
        {'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': '7'}]},
        'vault-alerts-v1',
        'ready',
        {
            'profile_key': 'vault-alerts-v1',
            'identity_observed': True,
            'vault_alert_sample': {'status': 'qualified', 'identity_observed': True, **counts},
        },
        _OBSERVED,
    )


@pytest.mark.parametrize('bad_value', [None, True, -1, '2', 1.5])
def test_unqualified_alert_count_never_passes_validation(bad_value: object) -> None:
    status, counts, observed = binding_coverage._qualified_alert_sample(
        binding_row=_qualified_sample(bad_value), source_id=7, now=_OBSERVED
    )
    assert status == 'needs_validation'
    assert counts is None
    assert observed is None


def test_qualified_alert_counts_retain_exact_consistency() -> None:
    status, counts, observed = binding_coverage._qualified_alert_sample(
        binding_row=_qualified_sample(), source_id=7, now=_OBSERVED
    )
    assert status == 'qualified'
    assert counts is not None
    assert counts['observed_rows'] == 2
    assert observed == _OBSERVED


def _posture() -> dict[str, Any]:
    return {
        'status': 'ready',
        'observed_stored_certificates': 2,
        'within_validity_window': 1,
        'not_yet_valid': 0,
        'expired': 1,
        'unknown': 0,
        'expires_within_7d': 1,
        'expires_8_to_30d': 0,
        'expires_after_30d': 0,
        'last_observed_at': _OBSERVED,
    }


@pytest.mark.parametrize('bad_value', [None, True, -1, '2', 1.5])
def test_unqualified_expiry_count_never_generates_recommendation(
    monkeypatch: pytest.MonkeyPatch, bad_value: object
) -> None:
    posture = _posture()
    posture['expired'] = bad_value
    monkeypatch.setattr(recommendations, 'build_stored_pki_validity_posture', lambda: posture)
    assert recommendations.build_secrets_pki_recommendation_findings({recommendations._RULE_KEY: {}}) == []


def test_valid_expiry_pressure_still_generates_bounded_public_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recommendations, 'build_stored_pki_validity_posture', _posture)
    findings = recommendations.build_secrets_pki_recommendation_findings({recommendations._RULE_KEY: {}})
    assert len(findings) == 1
    assert findings[0]['severity'] == 'critical'
    assert findings[0]['evidence']['observed_stored_certificates'] == 2
