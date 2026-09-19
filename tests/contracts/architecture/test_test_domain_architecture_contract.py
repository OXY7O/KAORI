from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_domain_first_test_architecture_is_release_gated() -> None:
    verifier = (ROOT / 'scripts/verify_test_domain_architecture.py').read_text(encoding='utf-8')
    quality_gate = (ROOT / 'scripts/quality_gate.sh').read_text(encoding='utf-8')

    assert 'RETIRED_FUNCTIONAL_ROOTS' in verifier
    assert 'RETIRED_PURPOSE_CHILDREN' in verifier
    assert 'RETIRED_CONTRACT_ROOTS' in verifier
    assert 'tests/kubernetes/analytics' in verifier
    assert 'tests/storage/object_storage/inventory' in verifier
    assert 'python scripts/verify_test_domain_architecture.py' in quality_gate
