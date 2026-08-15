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
    assert 'payload.report_type_groups' in page
    assert "'report_type_groups': _get_report_type_groups()" in service
    assert 'def _get_report_type_groups()' in service
    assert "('kubernetes', 'Kubernetes')" not in page
    assert "('object_storage', 'Object Storage')" not in page
    assert 'value: object_storage_inventory' in catalog
    assert 'value: object_storage_analysis' in catalog
    assert 'default_format: xlsx' in catalog
    assert 'default_format: pdf' in catalog
    assert "'object_storage_system_id':" in service
    assert 'ObjectStorageSystem' in service


def test_generate_exposes_selected_output_contract_without_repeating_global_family_policy() -> None:
    page = read('app/templates/reports/generate/index.html')

    assert 'data-report-output-contract="true"' in page
    assert 'Selected Artifact' in page
    assert 'Publication Contract' in page
    assert 'id="output-format-selected"' in page
    assert 'id="output-format-default"' in page
    assert 'id="output-format-purpose"' in page
    assert '>Allowed</span>' in page
    assert 'Governed workbook preserving inventory structure and tabular review.' in page
    assert 'Governed analytical publication for review, evidence, and operational communication.' in page
    assert 'Format Policy' not in page
    assert 'PDF only' not in page
    assert 'XLSX only' not in page
