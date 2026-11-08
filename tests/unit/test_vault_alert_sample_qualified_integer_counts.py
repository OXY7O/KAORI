"""Committed Vault Alert sample uses only exact, source-qualified integer counts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.secrets_pki.binding_coverage import _qualified_alert_sample


def _binding(now: datetime, *, overrides: dict[str, object] | None = None) -> tuple:
    sample: dict[str, object] = {
        'status': 'qualified',
        'identity_observed': True,
        'observed_rows': 4,
        'firing': 2,
        'suppressed': 1,
        'unprocessed': 1,
        'critical': 1,
        'warning': 2,
        'info': 1,
    }
    sample.update(overrides or {})
    return (
        '17',
        {'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': '17'}]},
        'vault-alerts-v1',
        'ready',
        {'profile_key': 'vault-alerts-v1', 'identity_observed': True, 'vault_alert_sample': sample},
        now,
    )


def test_qualified_committed_alert_counts_are_preserved() -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    status, counts, observed = _qualified_alert_sample(binding_row=_binding(now), source_id=17, now=now)

    assert status == 'qualified'
    assert counts is not None
    assert counts['observed_rows'] == 4
    assert counts['firing'] == 2
    assert counts['warning'] == 2
    assert observed == now


@pytest.mark.parametrize(
    ('field', 'invalid'),
    [
        ('observed_rows', None),
        ('firing', True),
        ('warning', -1),
        ('critical', '1'),
        ('info', 1.0),
        ('observed_rows', 3),
    ],
)
def test_unqualified_counts_never_create_ready_sample(field: str, invalid: object) -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    status, counts, observed = _qualified_alert_sample(
        binding_row=_binding(now, overrides={field: invalid}), source_id=17, now=now
    )

    assert status == 'needs_validation'
    assert counts is None
    assert observed is None


def test_unknown_binding_identity_stays_unqualified() -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    row = _binding(now)
    row = ('18', *row[1:])
    status, counts, observed = _qualified_alert_sample(binding_row=row, source_id=17, now=now)

    assert status == 'needs_validation'
    assert counts is None
    assert observed is None
