from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / 'app/reports/report_templates/service.py'
ROUTES = ROOT / 'app/reports/report_templates/routes.py'
TEMPLATE = ROOT / 'app/templates/reports/report_templates/index.html'
MODAL = ROOT / 'app/templates/reports/components/_record_detail_modal.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_template_registry_uses_full_width_kaori_workspace() -> None:
    template = read(TEMPLATE)

    assert 'data-report-templates-page="registry-v2"' in template
    assert 'Template Governance Posture' in template
    assert 'data-template-registry="true"' in template
    assert 'data-template-filters="true"' in template
    assert 'xl:grid-cols-6' in template
    assert 'Template Registry' in template
    assert '>Template<' in template
    assert '>Family<' in template
    assert '>Report Type<' in template
    assert '>Output<' in template
    assert '>Sections<' in template
    assert '>Ownership<' in template
    assert '>Action<' in template
    assert 'Previous' in template
    assert 'Next' in template
    assert 'templates-registry-loading' in template
    assert 'xl:grid-cols-[minmax(0,1fr)_420px]' not in template
    assert 'View more' not in template


def test_templates_use_native_modal_details_and_compact_custom_form() -> None:
    template = read(TEMPLATE)
    modal = read(MODAL)

    assert 'data-kaori-dialog-open' in template
    assert 'data-template-detail-modal=' in template
    assert 'Create Custom Template' in template
    assert 'Edit Custom Template' in template
    assert 'Fixed Inventory Workbook Structure' in template
    assert 'data-operation-submit' in template
    assert 'Delete Custom Template' in template
    assert 'onsubmit="return confirm' not in template
    assert '<dialog' in modal
    assert 'data-kaori-native-dialog' in modal
    assert 'data-kaori-dialog-size' in modal


def test_template_service_is_catalog_driven_and_filterable() -> None:
    service = read(SERVICE)

    assert 'for spec in REPORT_TYPE_SPECS' in service
    assert "'family': spec.family" in service
    assert 'template.source_template_key = f"system:{form_state[\'report_type\']}"' in service
    assert "'families': [" in service
    assert "'ownership': [" in service
    assert "'formats': [" in service
    assert "for key in ('family', 'report_type', 'ownership', 'status', 'output_format', 'search')" in service
    assert "'System Template'" in service
    assert "'Active Custom'" in service


def test_template_feedback_titles_follow_title_case() -> None:
    routes = read(ROUTES)

    assert "title='Report Template Validation Failed'" in routes
    assert "title='Report Template Created'" in routes
    assert "title='Report Template Updated'" in routes
    assert "title='Report Template Deleted' if success else 'Report Template Deletion Failed'" in routes
    assert "title='Report Template Duplicated' if success else 'Report Template Duplication Failed'" in routes
    assert "action_label='View Report Templates'" in routes
