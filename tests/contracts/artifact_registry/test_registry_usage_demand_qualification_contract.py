"""Demand counters require ready, finite and nonnegative Metrics Source evidence (#4617)."""

from types import SimpleNamespace

import pytest

from app.artifact_registry.presentation_analytics import _accumulate_metrics, _analytics_aggregate


@pytest.mark.parametrize("status", ["unavailable", "partial", "stale", None])
def test_unready_metrics_do_not_claim_observed_demand(status):
    aggregate = _analytics_aggregate()
    rows = []
    _accumulate_metrics(
        aggregate,
        {
            "status": status,
            "request_rate_per_second": 91,
            "backend_request_rate_per_second": 17,
            "inflight_requests": 8,
            "task_queue_size": 3,
            "project_pull_count": {"cached": 42},
        },
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=rows,
    )
    for key in (
        "request_rate_per_second",
        "backend_request_rate_per_second",
        "inflight_requests",
        "task_queue_size",
        "pull_activity",
    ):
        assert aggregate[key] == 0
    assert rows == []


def test_ready_metrics_reject_invalid_demand_but_keep_valid_observations():
    aggregate = _analytics_aggregate()
    _accumulate_metrics(
        aggregate,
        {
            "status": "ready",
            "request_rate_per_second": float("inf"),
            "backend_request_rate_per_second": -2,
            "inflight_requests": True,
            "task_queue_size": 5,
        },
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=[],
    )
    assert aggregate["request_rate_per_second"] == 0
    assert aggregate["backend_request_rate_per_second"] == 0
    assert aggregate["inflight_requests"] == 0
    assert aggregate["task_queue_size"] == 5


@pytest.mark.parametrize(
    ("health", "component", "expected_health", "expected_component"),
    [
        (True, True, 0, 0),
        (float("inf"), float("-inf"), 0, 0),
        (float("nan"), float("nan"), 0, 0),
        (-1, 0, 0, 0),
        (1, 1.0, 1, 1),
    ],
)
def test_provider_health_requires_finite_positive_numeric_evidence(
    health, component, expected_health, expected_component
):
    aggregate = _analytics_aggregate()
    _accumulate_metrics(
        aggregate,
        {
            "status": "ready",
            "provider_health_value": health,
            "component_up_value": component,
        },
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=[],
    )
    assert aggregate["healthy_providers"] == expected_health
    assert aggregate["component_up_providers"] == expected_component
