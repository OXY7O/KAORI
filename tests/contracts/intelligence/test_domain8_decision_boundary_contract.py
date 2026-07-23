from pathlib import Path


def test_decision_boundary_is_immutable_and_signed() -> None:
    source = Path('app/intelligence/decision.py').read_text()
    assert '@dataclass(frozen=True, slots=True)' in source
    assert 'class DecisionSnapshot' in source
    assert 'compute_evidence_hash' in source
    assert 'hmac.compare_digest' in source
    assert 'Executor requires a DecisionSnapshot' in source


def test_decision_carries_versioned_evidence_and_policy() -> None:
    source = Path('app/intelligence/decision.py').read_text()
    for field in (
        'rule_version',
        'knowledge_version',
        'evidence_hash',
        'inventory_generation',
        'alert_fingerprint',
        'policy',
        'expires_at',
    ):
        assert field in source
    assert "NEEDS_APPROVAL = 'needs_approval'" in source
    assert "BLOCKED = 'blocked'" in source
