from pathlib import Path


def test_inventory_refresh_uses_one_explicit_collection_timestamp() -> None:
    synchronization = Path('app/inventory/synchronization.py').read_text()
    persistence = Path('app/inventory/persistence.py').read_text()

    assert synchronization.count('collected_at = datetime.now(UTC)') == 1
    assert synchronization.count('collected_at,') >= 10
    assert persistence.count('collected_at: datetime,') == 10
    assert persistence.count('.collected_at = collected_at') == 10
