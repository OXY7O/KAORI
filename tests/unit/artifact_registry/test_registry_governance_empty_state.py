from __future__ import annotations

from app.artifact_registry.presentation_governance import _governance_replication_empty_state


def _counts(*, observed=0, unavailable=0, unsupported=0, unknown=0):
    return {
        'observed': observed,
        'unavailable': unavailable,
        'unsupported': unsupported,
        'unknown': unknown,
    }


def test_fully_observed_empty_replication_is_not_missing_evidence():
    result = _governance_replication_empty_state(
        provider_count=2, capability_counts=_counts(observed=2)
    )
    assert result['title'] == 'No Replication Policies Configured'
    assert 'successfully observed' in result['description']


def test_unsupported_replication_has_distinct_empty_state():
    result = _governance_replication_empty_state(
        provider_count=2, capability_counts=_counts(unsupported=2)
    )
    assert result['title'] == 'Replication Not Supported'


def test_failed_replication_collection_never_claims_no_policies():
    result = _governance_replication_empty_state(
        provider_count=2, capability_counts=_counts(observed=1, unavailable=1)
    )
    assert result['title'] == 'Replication Evidence Unavailable'


def test_mixed_observed_and_unknown_is_not_clean_empty():
    result = _governance_replication_empty_state(
        provider_count=2, capability_counts=_counts(observed=1, unknown=1)
    )
    assert result['title'] == 'No Replication Policies in Available Evidence'


def test_uncollected_scope_remains_explicit():
    result = _governance_replication_empty_state(
        provider_count=1, capability_counts=_counts(unknown=1)
    )
    assert result['title'] == 'No Replication Evidence Collected'
