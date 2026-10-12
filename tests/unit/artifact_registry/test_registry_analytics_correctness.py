from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from app.artifact_registry.analytics import _growth_payload
from app.artifact_registry.analytics_job_adapter import _analytics_snapshot_posture
from app.artifact_registry.presentation_analytics import _registry_analytics_scope
from app.artifact_registry.presentation_common import _analytics_snapshot_view


def test_growth_from_observed_zero_is_not_suppressed() -> None:
    now = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
    previous = SimpleNamespace(
        generated_at=now - timedelta(days=1),
        payload_json={'inventory': {'artifacts': 0, 'total_size_bytes': 0}},
    )
    growth, elapsed = _growth_payload(
        previous, generated_at=now, artifact_count=8, total_size=2048
    )
    assert elapsed == pytest.approx(1.0)
    assert growth['artifact_delta'] == 8
    assert growth['size_delta_bytes'] == 2048
    assert growth['artifact_growth_per_day'] == pytest.approx(8)


def test_expired_analytics_snapshot_is_not_current() -> None:
    now = datetime.now(UTC)
    snapshot = SimpleNamespace(
        status='ready',
        payload_json={'inventory': {'artifacts': 3}},
        generated_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
    )
    assert _analytics_snapshot_view(snapshot)['is_current'] is False
    assert _analytics_snapshot_view(snapshot)['is_stale'] is True


def test_missing_expiry_is_not_usable_current_evidence() -> None:
    snapshot = SimpleNamespace(
        status='ready',
        payload_json={'inventory': {}},
        generated_at=datetime.now(UTC),
        expires_at=None,
    )
    assert _analytics_snapshot_view(snapshot)['is_current'] is False


def test_invalid_registry_selection_never_widens_to_all_sources() -> None:
    providers = [SimpleNamespace(id=3), SimpleNamespace(id=9)]
    assert _registry_analytics_scope(None, providers) is None
    assert _registry_analytics_scope(9, providers) == 9
    with pytest.raises(NotFound):
        _registry_analytics_scope(17, providers)


def test_partial_and_expired_fleet_cannot_be_declared_current() -> None:
    label, tone, _ = _analytics_snapshot_posture(
        eligible_count=2, covered_count=2, current_count=1
    )
    assert label == 'Partial Coverage'
    assert tone == 'warning'
    label, tone, _ = _analytics_snapshot_posture(
        eligible_count=2, covered_count=2, current_count=0
    )
    assert label == 'Stale Snapshot'
    assert tone == 'warning'
