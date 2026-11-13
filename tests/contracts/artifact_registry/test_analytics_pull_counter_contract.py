"""Regression coverage for evidence-qualified Registry pull counters (#4617)."""

from types import SimpleNamespace

from app.artifact_registry.presentation_analytics import _accumulate_metrics, _analytics_aggregate


def test_pull_activity_rejects_invalid_counter_values():
    aggregate = _analytics_aggregate()
    rows = []
    identity = SimpleNamespace(name="harbor-a", provider_key="harbor")
    _accumulate_metrics(
        aggregate,
        {
            "status": "ready",
            "project_pull_count": {
                "valid": 12,
                "zero": 0,
                "negative": -4,
                "boolean": True,
                "infinite": float("inf"),
                "missing": None,
                "text": "15",
            },
        },
        identity=identity,
        activity_rows=rows,
    )

    assert aggregate["pull_activity"] == 12
    assert [(row["project_name"], row["pull_count"]) for row in rows] == [
        ("valid", 12.0),
        ("zero", 0.0),
    ]


def test_missing_pull_series_does_not_create_project_rows():
    aggregate = _analytics_aggregate()
    rows = []
    _accumulate_metrics(
        aggregate,
        {"status": "unavailable", "project_pull_count": None},
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=rows,
    )
    assert rows == []
    assert aggregate["pull_activity"] == 0

def test_unavailable_metrics_with_cached_pull_values_do_not_claim_observed_usage():
    aggregate = _analytics_aggregate()
    rows = []
    _accumulate_metrics(
        aggregate,
        {"status": "unavailable", "project_pull_count": {"cached-project": 42}},
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=rows,
    )
    assert aggregate["metrics_ready"] == 0
    assert aggregate["pull_activity"] == 0
    assert rows == []
