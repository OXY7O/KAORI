from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_reports_overview_identity_and_hero_copy_are_explicit() -> None:
    service = read('app/reports/overview/service.py')
    presentation = read('app/reports/overview/presentation.py')
    page = read('app/templates/reports/overview/index.html')

    assert "'page_title': 'Reports Overview'" in service
    assert "normalized.setdefault('page_title', 'Reports Overview')" in presentation
    assert '{% block title %}Reports Overview{% endblock title %}' in page
    assert 'reporting artifacts across connected' in service
    assert 'infrastructure scopes with clear readiness, storage, and lifecycle context.' in service


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
        'overview': 'infrastructure scopes with clear readiness, storage, and lifecycle context',
        'generate': 'selected scope, reusable sections, and an approved output contract',
        'generated': 'worker execution, retained artifact delivery, and lifecycle review',
        'generated_detail': 'selected scope, retained artifact, execution evidence, and delivery readiness',
        'templates': 'preserving the canonical reporting contract',
        'schedules': 'timezone-aware contracts with retained execution evidence',
        'storage': 'retention readiness, and backend health before generation or retrieval operations',
    }
    for key, fragment in expected_fragments.items():
        assert fragment in files[key]


def test_reports_overview_uses_operational_reading_and_contract_boundary_not_generic_tips() -> None:
    posture = read('app/templates/reports/overview/partials/_reporting_operational_posture.html')
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')

    assert 'Operational Reading' in posture
    assert 'Performance Tip' not in posture
    assert 'Completion Rate measures resolved requests only' in posture
    assert 'Artifact Estate &amp; Report Capability' in estate
    assert 'Contracts &amp; Automation' in estate
    assert 'Output Contract' in estate
    assert 'Format Tip' not in estate
    assert 'Analytics contracts expose PDF or CSV' in estate
    assert 'Inventory contracts expose XLSX or CSV' in estate


def test_planned_report_coverage_is_definition_owned_not_embedded_in_overview_service() -> None:
    service = read('app/reports/overview/service.py')
    catalog = read('app/reports/catalog.py')
    document = yaml.safe_load(read('app/definitions/catalogs/reports/coverage.yaml'))

    assert document['schema_version'] == 1
    assert document['kind'] == 'report_coverage_catalog'
    assert {item['key'] for item in document['domains']} == {'server', 'hci'}
    assert 'SERVER_REPORT_TYPE_COVERAGE' not in service
    assert 'HCI_REPORT_TYPE_COVERAGE' not in service
    assert 'PLANNED_REPORT_COVERAGE_DOMAINS' in service
    assert "load_definition_document('reports/coverage.yaml'" in catalog
