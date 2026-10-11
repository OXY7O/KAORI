from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.kubernetes.governance.tls_certificates.sync_state import _collection_freshness


def state(secret='collected', ingress='collected', at=None):
    return SimpleNamespace(
        secret_collection_status=secret,
        ingress_mapping_status=ingress,
        collected_at=at,
    )


def test_failed_attempt_cannot_refresh_successful_snapshot_clock():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    old = now - timedelta(days=2)
    # A failure can update state.updated_at but cannot establish freshness.
    failed = state(secret='collection_failed', ingress='collected', at=now)
    failed.updated_at = now
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a'], states={'a': failed},
        record_times={'a': old}, stale_after=timedelta(hours=7), now=now,
    )
    assert at == old
    assert stale is True
    assert exceptions is True


def test_zero_certificates_can_have_successful_collection_evidence():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a'], states={'a': state(at=now)},
        record_times={}, stale_after=timedelta(hours=7), now=now,
    )
    assert at == now and stale is False and exceptions is False


def test_fleet_requires_all_clusters_and_all_source_families():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    earlier = now - timedelta(hours=15)
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a', 'b', 'c'],
        states={
            'a': state(at=now),
            'b': state(ingress='permission_unavailable', at=earlier),
        },
        record_times={'b': earlier},
        stale_after=timedelta(hours=7),
        now=now,
    )
    assert at == now
    assert stale is True
    assert exceptions is True


def test_recent_secret_evidence_does_not_make_failed_ingress_mapping_complete():
    now = datetime(2026, 10, 11, tzinfo=UTC)
    at, stale, exceptions = _collection_freshness(
        cluster_ids=['a'], states={'a': state(ingress='api_unavailable', at=now)},
        record_times={}, stale_after=timedelta(hours=7), now=now,
    )
    assert at == now and stale is False and exceptions is True
