from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

INVENTORY_ROOTS = (
    'app/kubernetes/inventory',
    'app/storage/object_storage/inventory',
    'app/templates/kubernetes/inventory',
    'app/templates/storage/object_storage/inventory',
)

FORBIDDEN_OWNERSHIP_TOKENS = (
    'get_active_recommendation_findings',
    'get_dashboard_recommendation_findings',
    'intelligence.recommendation_details',
    'alert_intelligence.index',
    'Alert Intelligence',
    'Recommended Actions',
)


def inventory_source() -> str:
    chunks: list[str] = []
    for relative in INVENTORY_ROOTS:
        root = ROOT / relative
        for path in root.rglob('*'):
            if path.suffix in {'.py', '.html'}:
                chunks.append(path.read_text(encoding='utf-8'))
    return '\n'.join(chunks)


def test_inventory_remains_factual_asset_truth_without_operational_ownership() -> None:
    source = inventory_source()

    for token in FORBIDDEN_OWNERSHIP_TOKENS:
        assert token not in source, token
