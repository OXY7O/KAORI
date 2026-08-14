from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CONTRACT_DIR = ROOT / 'tests/contracts/inventory/object_storage'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_bucket_modal_width_contract_matches_current_professional_surface() -> None:
    template = read('app/templates/inventory/object_storage/buckets/partials/_table_content.html')
    assert 'max-w-[88rem]' in template
    assert 'max-w-6xl' not in template


def test_storage_inventory_contracts_do_not_lock_retired_bucket_modal_width() -> None:
    stale = []
    for path in CONTRACT_DIR.glob('test_*.py'):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding='utf-8')
        if "assert 'max-w-6xl'" in text:
            stale.append(path.name)
    assert not stale, f'Retired max-w-6xl contract remains in: {stale}'
