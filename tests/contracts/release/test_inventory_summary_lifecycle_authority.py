from pathlib import Path


LEGACY_SUMMARY = Path('app/templates/kubernetes/inventory/components/_summary.html')
INTELLIGENCE_CONTRACT = Path(
    'tests/contracts/intelligence/test_intelligence_workspace_standard_contract.py'
)


def test_retired_inventory_summary_has_no_stale_contract_consumer() -> None:
    contract = INTELLIGENCE_CONTRACT.read_text(encoding='utf-8')

    assert not LEGACY_SUMMARY.exists()
    assert LEGACY_SUMMARY.as_posix() not in contract
