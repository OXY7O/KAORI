from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.artifact_registry.presentation_common import _analytics_snapshot_view
from app.artifact_registry.presentation_overview import _fleet_freshness


def _snapshot(*, expired: bool = False, payload: bool = True, expiry: bool = True):
    now = datetime.now(UTC)
    return SimpleNamespace(
        status='ready',
        payload_json={'metrics': {'status': 'ready'}} if payload else None,
        generated_at=now - timedelta(hours=3) if expired else now - timedelta(minutes=5),
        expires_at=(now - timedelta(minutes=1) if expired else now + timedelta(minutes=20)) if expiry else None,
    )


@pytest.mark.parametrize(
    ('snapshot', 'label', 'current', 'stale'),
    [
        (None, 'Not Materialized', False, False),
        (_snapshot(), 'Current Snapshot', True, False),
        (_snapshot(expired=True), 'Stale Snapshot', False, True),
        (_snapshot(expiry=False), 'Unavailable', False, False),
        (_snapshot(payload=False), 'Unavailable', False, False),
    ],
)
def test_selected_analytics_evidence_requires_usable_ready_payload(
    snapshot, label, current, stale, monkeypatch,
) -> None:
    from app.artifact_registry import presentation_common

    # This fixture tests local expiry/state classification in isolation.
    # Source generation comparisons have dedicated, DB-backed tests.
    monkeypatch.setattr(presentation_common, '_registry_analytics_inputs_changed', lambda _snapshot: False)
    view = _analytics_snapshot_view(snapshot)
    assert view['label'] == label
    assert view['is_current'] is current
    assert view['is_stale'] is stale


@pytest.mark.parametrize(
    ('current', 'stale', 'total', 'label'),
    [
        (2, 0, 2, 'Ready'),
        (1, 1, 2, 'Partial'),
        (1, 0, 2, 'Partial'),
        (0, 2, 2, 'Stale'),
        (0, 1, 2, 'Stale'),
        (0, 0, 2, 'Required'),
        (0, 0, 0, 'Required'),
    ],
)
def test_fleet_analytics_never_calls_expired_evidence_ready(
    current: int, stale: int, total: int, label: str,
) -> None:
    context = {
        'latest_committed_at': None,
        'stale_snapshot_count': 0,
        'failed_refresh_count': 0,
    }
    stats = {
        'committed_count': 0,
        'metrics_ready_count': 0,
        'artifact_total': 0,
        'scanned_count': 0,
        'analytics_ready_count': current,
        'analytics_stale_count': stale,
        'latest_security_at': None,
        'latest_analytics_at': None,
    }
    cards = _fleet_freshness(context=context, provider_count=total, stats=stats)
    analytics = next(card for card in cards if card['label'] == 'Analytics Snapshot')
    assert analytics['status'] == label
    assert analytics['tone'] == ('normal' if label == 'Ready' else 'unknown' if label == 'Required' else 'warning')
