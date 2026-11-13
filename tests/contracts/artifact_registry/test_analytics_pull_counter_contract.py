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

def test_pull_activity_excludes_missing_project_identity_without_losing_valid_counts():
    aggregate = _analytics_aggregate()
    rows = []
    _accumulate_metrics(
        aggregate,
        {
            "status": "ready",
            "project_pull_count": {
                "": 100,
                "  ": 200,
                None: 300,
                42: 400,
                "observed-project": 7,
            },
        },
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=rows,
    )
    assert aggregate["pull_activity"] == 7
    assert [(row["project_name"], row["pull_count"]) for row in rows] == [
        ("observed-project", 7.0),
    ]


def test_pull_activity_rejects_padded_project_names_without_misattribution():
    aggregate = _analytics_aggregate()
    rows = []
    _accumulate_metrics(
        aggregate,
        {
            "status": "ready",
            "project_pull_count": {
                " production": 50,
                "production ": 60,
                "production": 7,
            },
        },
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=rows,
    )
    assert aggregate["pull_activity"] == 7
    assert [(row["project_name"], row["pull_count"]) for row in rows] == [
        ("production", 7.0),
    ]


def test_zero_pull_count_is_not_reported_as_project_activity():
    aggregate = _analytics_aggregate()
    rows = []
    _accumulate_metrics(
        aggregate,
        {"status": "ready", "project_pull_count": {"idle-project": 0, "active-project": 3}},
        identity=SimpleNamespace(name="harbor-a", provider_key="harbor"),
        activity_rows=rows,
    )
    assert aggregate["pull_activity"] == 3
    assert [(row["project_name"], row["pull_count"]) for row in rows] == [
        ("active-project", 3.0),
    ]
