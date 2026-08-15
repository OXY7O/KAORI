from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_generate_keeps_only_published_scope_contracts_until_object_storage_scope_is_implemented() -> None:
    page = read('app/templates/reports/generate/index.html')
    catalog = read('app/definitions/catalogs/reports/coverage.yaml')

    assert 'Single Cluster Scope' in page
    assert 'Kubernetes Scope' in page
    assert 'Object Storage Inventory Report' in catalog
    assert 'Object Storage Capacity Analysis Report' in catalog
    assert 'Object Storage Inventory Report' not in page
    assert 'Object Storage Capacity Analysis Report' not in page


def test_generate_exposes_canonical_family_format_policy() -> None:
    page = read('app/templates/reports/generate/index.html')

    assert 'data-report-format-policy="true"' in page
    assert 'PDF default · CSV data export' in page
    assert 'XLSX default · CSV flat export' in page
    assert 'PDF only' not in page
    assert 'XLSX only' not in page
