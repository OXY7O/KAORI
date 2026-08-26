import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def has_python_string(source: str, expected: str) -> bool:
    return any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and expected in node.value
        for node in ast.walk(ast.parse(source))
    )


def test_reports_overview_identity_and_hero_copy_are_explicit() -> None:
    service = read('app/reports/overview/service.py')
    presentation = read('app/reports/overview/presentation.py')
    page = read('app/templates/reports/overview/index.html')

    assert "'page_title': 'Reports Overview'" in service
    assert "normalized.setdefault('page_title', 'Reports Overview')" in presentation
    assert '{% block title %}Reports Overview{% endblock title %}' in page
    assert 'report coverage across managed infrastructure' in service


def test_report_workspace_hero_descriptions_keep_consistent_operational_depth() -> None:
    files = {
        'overview': read('app/reports/overview/service.py'),
        'generate': read('app/reports/generate/service.py'),
        'generated': read('app/templates/reports/generated/index.html'),
        'generated_detail': read('app/templates/reports/generated/detail.html'),
        'templates': read('app/reports/report_templates/service.py'),
        'schedules': read('app/reports/schedules/service.py'),
        'storage': read('app/reports/storage/service.py'),
    }

    expected_fragments = {
        'overview': 'report coverage across managed infrastructure',
        'generate': 'scope, sections, and an approved output format',
        'generated': 'worker execution progress, artifact readiness, storage availability, and lifecycle state',
        'generated_detail': 'report scope, artifact evidence, execution state, and delivery readiness',
        'templates': 'protected system templates and reusable custom report structures',
        'schedules': 'timezone-aware schedules and retained run evidence',
        'storage': 'backend and reference integrity, verification results, retained coverage, and lifecycle ownership',
    }
    for key, fragment in expected_fragments.items():
        if key in {'templates', 'storage'}:
            assert has_python_string(files[key], fragment)
        else:
            assert fragment in files[key]


def test_reports_overview_uses_operational_reading_and_contract_boundary_not_generic_tips() -> None:
    posture = read('app/templates/reports/overview/partials/_reporting_operational_posture.html')
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')

    assert 'Operational Reading' in posture
    assert 'Performance Tip' not in posture
    assert 'Completion Rate measures resolved requests only' in posture
    assert 'Report Coverage &amp; Artifact Estate' in estate
    assert 'Contracts &amp; Automation' in estate
    assert 'Retained Artifact Mix' in estate
    assert 'Published Contract Families' in estate
    assert 'Automation Boundary' in estate
    assert 'Output Contract' in estate
    assert 'Format Tip' not in estate
    assert 'Published formats stay family-owned' in estate
    assert 'Published contracts are admitted to Generate' in estate
    assert 'Analytics Reports' in estate and 'PDF · XLSX · CSV' in estate
    assert 'Inventory Reports' in estate and 'XLSX · CSV' in estate
    assert 'Candidate Domains' in estate and 'Contract + renderer required' in estate
    assert 'text-[' not in estate


def test_planned_report_coverage_is_definition_owned_not_embedded_in_overview_service() -> None:
    service = read('app/reports/overview/service.py')
    catalog = read('app/reports/catalog.py')
    document = yaml.safe_load(read('app/definitions/catalogs/reports/coverage.yaml'))

    assert document['schema_version'] == 1
    assert document['kind'] == 'report_coverage_catalog'
    assert {item['key'] for item in document['domains']} == {'object_storage', 'server', 'hci'}
    object_storage = next(item for item in document['domains'] if item['key'] == 'object_storage')
    assert object_storage['status'] == 'Published'
    assert object_storage['tone'] == 'normal'
    assert len(object_storage['items']) == 3
    assert 'SERVER_REPORT_TYPE_COVERAGE' not in service
    assert 'HCI_REPORT_TYPE_COVERAGE' not in service
    assert 'REPORT_COVERAGE_DOMAINS' in service
    assert "load_definition_document('reports/coverage.yaml'" in catalog


def test_reports_overview_surfaces_object_storage_without_overclaiming_generate_support() -> None:
    service = read('app/reports/overview/service.py')
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')
    coverage = yaml.safe_load(read('app/definitions/catalogs/reports/coverage.yaml'))

    object_storage = next(item for item in coverage['domains'] if item['key'] == 'object_storage')
    assert object_storage['status'] == 'Published'
    assert 'Two canonical Object Storage report contracts are published' in object_storage['description']
    assert 'Object Storage Inventory Report' not in {item['name'] for item in object_storage['items']}
    assert 'Object Storage Forecast Report' in {item['name'] for item in object_storage['items']}
    assert "'status': 'Published'" in service
    assert "'published_count': len(published_items)" in service
    assert 'Reporting Domain Coverage' in estate
    assert 'Only Published contracts are selectable in Generate.' in estate
    assert 'Published means both a canonical report contract and renderer are registered' in estate


def test_reports_overview_does_not_execute_legacy_unrendered_context_builders() -> None:
    service = read('app/reports/overview/service.py')
    payload_body = service.split('def get_reports_overview_payload()', 1)[1].split(
        '\n\ndef get_report_architecture_context', 1
    )[0]

    assert 'get_notification_delivery_context()' not in payload_body
    assert 'get_pipeline_status(' not in payload_body
    assert 'get_current_status(' not in payload_body
    assert 'get_reporting_context(' not in payload_body
    assert 'get_reporting_operating_model(' not in payload_body
    assert 'get_data_collection_status(' not in payload_body
    assert "'report_type_coverage': report_type_coverage" in payload_body
    assert "'reporting_operations': get_reporting_operations" in payload_body
