from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CONTRACT_DIR = ROOT / 'tests/contracts/storage/object_storage/inventory'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_inventory_modal_uses_shared_92rem_professional_surface() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')
    systems = read('app/templates/storage/object_storage/inventory/systems/index.html')
    buckets = read('app/templates/storage/object_storage/inventory/buckets/index.html')

    assert "'max-w-[92rem]'" in modal
    assert 'resource_detail_modal.inventory_host(' in systems
    assert 'resource_detail_modal.inventory_host(' in buckets
    assert 'max-w-[88rem]' not in systems
    assert 'max-w-[88rem]' not in buckets


def test_storage_inventory_contracts_do_not_lock_retired_bucket_modal_width() -> None:
    stale = []
    for path in CONTRACT_DIR.glob('test_*.py'):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding='utf-8')
        if "assert 'max-w-6xl'" in text:
            stale.append(path.name)
    assert not stale, f'Retired max-w-6xl contract remains in: {stale}'
