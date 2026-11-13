"""Regression coverage for observed-only Registry governance policy ratios (#4619)."""

from app.artifact_registry.presentation_analytics import _governance_policy_coverage


def _aggregate(*, assessed=0, retention=0, retention_missing=0, immutability=0, immutability_missing=0):
    return {
        'governance_projects_assessed': assessed,
        'retention_configured': retention,
        'retention_not_configured': retention_missing,
        'immutability_configured': immutability,
        'immutability_not_configured': immutability_missing,
    }


def test_governance_coverage_requires_observed_policy_evidence():
    assert _governance_policy_coverage(_aggregate(), 'retention') is None
    assert _governance_policy_coverage(_aggregate(assessed=5), 'retention') is None


def test_governance_coverage_excludes_unobserved_projects_from_denominator():
    evidence = _aggregate(assessed=10, retention=2, retention_missing=2)
    assert _governance_policy_coverage(evidence, 'retention') == 50.0
    assert _governance_policy_coverage(evidence, 'immutability') is None


def test_governance_coverage_rejects_inconsistent_committed_counters():
    evidence = _aggregate(assessed=2, retention=3, retention_missing=1)
    assert _governance_policy_coverage(evidence, 'retention') is None


def test_governance_coverage_keeps_explicit_not_configured_distinct():
    evidence = _aggregate(assessed=3, immutability=0, immutability_missing=3)
    assert _governance_policy_coverage(evidence, 'immutability') == 0.0
