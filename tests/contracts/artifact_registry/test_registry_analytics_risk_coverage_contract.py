"""Regression coverage for bounded committed Registry risk posture (#4618)."""

from app.artifact_registry.presentation_analytics import _analytics_coverage


def _counts(**overrides):
    values = {
        "artifacts": 10,
        "projects": 4,
        "scanned_artifacts": 5,
        "signed_artifacts": 2,
        "sbom_artifacts": 3,
        "retention_configured": 1,
        "immutability_configured": 2,
    }
    return {**values, **overrides}


def test_risk_coverage_is_bounded_when_provider_counts_exceed_estate():
    coverage = _analytics_coverage(
        _counts(scanned_artifacts=14, signed_artifacts=-2, retention_configured=9)
    )
    assert coverage["scan"] == 100.0
    assert coverage["signature"] == 0.0
    assert coverage["retention"] == 100.0
    assert coverage["sbom"] == 30.0


def test_risk_coverage_without_denominator_is_unknown_not_clean():
    coverage = _analytics_coverage(_counts(artifacts=0, projects=0))
    assert all(value is None for value in coverage.values())


def test_risk_coverage_preserves_valid_observed_percentages():
    coverage = _analytics_coverage(_counts())
    assert coverage == {
        "scan": 50.0,
        "signature": 20.0,
        "sbom": 30.0,
        "retention": 25.0,
        "immutability": 50.0,
    }
