"""Prevent stale PKI issuer/certificate snapshots from appearing current."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.secrets_pki.pki_collection_freshness import qualified_committed_pki_count

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def _source(**overrides):
    state = {
        'status': 'ready',
        'observed_issuer_count': 1,
        'observed_stored_certificate_count': 1,
        'last_observed_at': NOW - timedelta(minutes=5),
        'last_committed_at': NOW - timedelta(minutes=4),
    }
    state.update(overrides)
    return SimpleNamespace(**state)


def _count(state, field='observed_issuer_count', max_count=24):
    return qualified_committed_pki_count(
        state,
        instant=NOW,
        count_field=field,
        max_count=max_count,
    )


def test_fresh_qualified_nonempty_and_committed_empty():
    assert _count(_source()) == 1
    assert _count(_source(observed_issuer_count=0)) == 0


@pytest.mark.parametrize('delta', [-1, 0, 1])
def test_current_generation_boundary_is_within_last_24_hours(delta):
    observed = NOW - timedelta(hours=24) + timedelta(seconds=delta)
    committed = observed
    result = _count(_source(last_observed_at=observed, last_committed_at=committed))
    assert (result == 1) is (delta >= 0)


@pytest.mark.parametrize(
    'change',
    [
        {'status': 'stale'},
        {'status': 'failed'},
        {'status': 'partial'},
        {'last_observed_at': None},
        {'last_committed_at': None},
        {'last_observed_at': NOW + timedelta(seconds=1)},
        {'last_committed_at': NOW + timedelta(seconds=1)},
        {'last_committed_at': NOW - timedelta(minutes=6)},
        {'observed_issuer_count': -1},
        {'observed_issuer_count': 25},
        {'observed_issuer_count': True},
        {'observed_issuer_count': '1'},
    ],
)
def test_unknown_failed_future_malformed_or_out_of_range_is_not_a_zero(change):
    assert _count(_source(**change)) is None


def test_sqlite_naive_timestamps_are_treated_as_utc():
    state = _source(
        last_observed_at=(NOW - timedelta(minutes=5)).replace(tzinfo=None),
        last_committed_at=(NOW - timedelta(minutes=4)).replace(tzinfo=None),
    )
    assert _count(state) == 1


def test_stored_public_certificate_bound_and_clock_freshness():
    state = _source(observed_stored_certificate_count=64)
    assert _count(state, field='observed_stored_certificate_count', max_count=64) == 64
    state.observed_stored_certificate_count = 65
    assert _count(state, field='observed_stored_certificate_count', max_count=64) is None


def test_presentations_use_current_freshness_gate_before_exposing_count():
    root = Path(__file__).resolve().parents[2]
    for filename, count_field in (
        ('pki_presentation.py', 'observed_issuers'),
        ('pki_stored_presentation.py', 'observed_certificates'),
    ):
        source = (root / 'app/secrets_pki' / filename).read_text(encoding='utf-8')
        assert 'qualified_committed_pki_count(' in source
        assert "state == 'committed'" in source
        assert f'{count_field}=sum(' in source
        assert 'if qualified else None' in source
        assert "integration_instance.provider_key != 'vault'" in source


def test_worker_retained_stale_snapshot_must_not_be_reported_current():
    for count_field in ('observed_issuer_count', 'observed_stored_certificate_count'):
        state = _source(
            status='stale',
            last_observed_at=NOW - timedelta(days=3),
            last_committed_at=NOW - timedelta(days=3),
        )
        assert _count(state, field=count_field, max_count=64) is None
