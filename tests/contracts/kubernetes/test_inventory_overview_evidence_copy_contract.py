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


def test_current_cluster_snapshot_guidance_is_concise_and_state_scoped() -> None:
    source = read('app/kubernetes/inventory/overview.py')
    guidance = source.split('def _inventory_guidance(', 1)[1].split('def get_cluster_by_id(', 1)[0]

    assert "'title': 'Snapshot Ready for Review'" in guidance
    assert "'description': 'Snapshot current; no active signals. Review assets.'" in guidance
    assert "'title': 'Review Collection Coverage'" in guidance
    assert "'title': 'Review Inventory Signals'" in guidance
    assert "'title': 'Refresh the Inventory Snapshot'" in guidance
    assert 'The committed snapshot is current and no inventory signals require immediate' not in guidance
