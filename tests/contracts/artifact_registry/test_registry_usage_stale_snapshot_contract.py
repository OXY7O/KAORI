"""Regression coverage for stale committed Registry Usage evidence (#4617)."""

from types import SimpleNamespace

import pytest

from app.artifact_registry import presentation_analytics as analytics


@pytest.mark.parametrize(
    ("is_current", "expected_pulls", "expected_ready"),
    [(False, 0.0, 0), (True, 7.0, 1)],
)
def test_stale_snapshot_cannot_contribute_current_usage(monkeypatch, is_current, expected_pulls, expected_ready):
    snapshot = SimpleNamespace(
        payload_json={
            "metrics": {
                "status": "ready",
                "project_pull_count": {"example": 7},
                "request_rate_per_second": 12,
            }
        }
    )

    class SnapshotQuery:
        def filter_by(self, **_kwargs):
            return self

        def order_by(self, *_args):
            return self

        def first(self):
            return snapshot

    monkeypatch.setattr(analytics.RegistryAnalyticsSnapshot, "query", SnapshotQuery())
    monkeypatch.setattr(analytics.RegistryAnalyticsSnapshot, "generated_at", None, raising=False)
    monkeypatch.setattr(analytics.RegistryAnalyticsSnapshot, "id", None, raising=False)
    monkeypatch.setattr(analytics, "analytics_snapshot_matches_window", lambda *_args: True)
    monkeypatch.setattr(
        analytics,
        "_analytics_snapshot_view",
        lambda identity, materialized: {
            "identity": identity,
            "snapshot": materialized,
            "is_current": is_current,
        },
    )

    identity = SimpleNamespace(id=1, name="Registry", provider_key="harbor")
    result = analytics._collect_analytics_rows([identity])
    assert result["aggregate"]["pull_activity"] == expected_pulls
    assert result["aggregate"]["metrics_ready"] == expected_ready
    assert result["aggregate"]["request_rate_per_second"] == (12.0 if is_current else 0.0)
    assert len(result["activity_rows"]) == (1 if is_current else 0)
