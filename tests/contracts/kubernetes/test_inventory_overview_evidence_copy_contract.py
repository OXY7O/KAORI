from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_zero_snapshot_does_not_claim_collected_object_count() -> None:
    hero = read('app/templates/kubernetes/inventory/overview/partials/_hero.html')
    assert "overview.health.synced_clusters else 'No Committed Objects'" in hero
    assert "' Collected Objects'" in hero


def test_unknown_connection_guidance_requires_verification_not_reconnection() -> None:
    source = read('app/kubernetes/inventory/overview.py')
    assert "'Verify Cluster Connection'" in source
    assert "'Not Observed', 'unknown'" in source
    assert "else 'Check provider readiness: the cluster connection state has not been observed.'" in source
