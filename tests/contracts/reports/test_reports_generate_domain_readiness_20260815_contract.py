from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_generate_publishes_object_storage_scope_contracts_only_after_generic_scope_is_implemented() -> None:
    page = read('app/templates/reports/generate/index.html')
    catalog = read('app/definitions/catalogs/reports/catalog.yaml')
    service = read('app/reports/generate/service.py')

    assert 'Infrastructure Asset Scope' in page
    assert 'Infrastructure Scope' in page
    assert 'id="object-storage-system-select"' in page
    assert 'data-report-scope-panel="object_storage_system"' in page
    assert "('object_storage', 'Object Storage')" in page
    assert 'value: object_storage_inventory' in catalog
    assert 'value: object_storage_analysis' in catalog
    assert 'default_format: xlsx' in catalog
    assert 'default_format: pdf' in catalog
    assert "'object_storage_system_id':" in service
    assert 'ObjectStorageSystem' in service


def test_generate_exposes_canonical_family_format_policy() -> None:
    page = read('app/templates/reports/generate/index.html')

    assert 'data-report-format-policy="true"' in page
    assert 'PDF default · CSV data export' in page
    assert 'XLSX default · CSV flat export' in page
    assert 'PDF only' not in page
    assert 'XLSX only' not in page
