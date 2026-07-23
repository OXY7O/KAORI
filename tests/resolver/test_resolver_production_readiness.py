import pytest

from app.resolver.production_readiness import (
    REQUIRED_CHECKS,
    ProductionReadinessError,
    assess_readiness,
    canonical_evidence_hash,
)


def passing_results():
    return {name: True for name in REQUIRED_CHECKS}


def test_complete_evidence_is_ready_and_hash_is_deterministic():
    results = passing_results()
    assessment = assess_readiness(results=results)
    assert assessment.ready is True
    assert assessment.failed_checks == ()
    assert assessment.evidence_hash == canonical_evidence_hash(dict(reversed(list(results.items()))))


def test_missing_failure_mode_check_blocks_readiness():
    results = passing_results()
    results['worker_loss_recovery'] = False
    assessment = assess_readiness(results=results)
    assert assessment.ready is False
    assert assessment.failed_checks == ('worker_loss_recovery',)


def test_unknown_check_is_rejected():
    with pytest.raises(ProductionReadinessError, match='Unknown production readiness checks'):
        assess_readiness(results={**passing_results(), 'skip_safety': True})
