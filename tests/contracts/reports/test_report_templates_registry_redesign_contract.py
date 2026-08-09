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
    assert 'data-template-posture="governance-v2"' in template
    assert 'Protected Base. Governed Customization.' in template
    assert 'data-template-governance-guardrails="true"' in template
    assert 'data-template-governance-coverage="true"' in template
    assert 'Catalog Coverage' in template
    assert 'Customization State' in template
    assert 'Tip: Use custom templates only for reusable reporting defaults.' in template
    assert 'Custom templates remain optional.' not in template
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
    assert 'components/loading_bar.html' in template
    assert "loading_bar.render('templates-registry-loading', active=false, label='Refreshing Template Registry')" in template
    assert 'data-kaori-template-loading-region="true"' in template
    assert 'hx-indicator="#templates-registry-loading"' in template
    assert '<input type="hidden" name="per_page" value="{{ payload.pagination.per_page }}">' in template
    assert 'data-template-page-size-form="true"' in template
    assert 'data-kaori-page-size-control="report-templates"' in template
    assert 'id="templates-registry-request-scope"' in template
    assert template.count('hx-sync="#templates-registry-request-scope:replace"') >= 3
    assert 'hx-trigger="change from:select"' in template
    assert 'hx-include="closest form"' not in template
    assert 'htmx-indicator h-0.5 overflow-hidden bg-kaori-soft' not in template
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
    assert "'system_count': system_count" in service
    assert "'custom_count': custom_count" in service
    assert "'active_custom_count': active_custom_count" in service
    assert "'Active Custom'" in service
    assert "'protected_coverage_percent': protected_coverage_percent" in service
    assert "'supported_formats_label': ' · '.join(supported_formats)" in service
    assert 'def normalize_templates_per_page(value: str | int | None) -> int:' in service
    assert 'requested_per_page = normalize_templates_per_page' in service
    assert "params: dict[str, str] = {'page': str(page), 'per_page': str(per_page)}" in service
    assert "for key in ('family', 'report_type', 'ownership', 'status', 'output_format', 'search')" in service


def test_template_feedback_titles_follow_title_case() -> None:
    routes = read(ROUTES)

    assert "title='Report Template Validation Failed'" in routes
    assert "title='Report Template Created'" in routes
    assert "title='Report Template Updated'" in routes
    assert "title='Report Template Deleted' if success else 'Report Template Deletion Failed'" in routes
    assert "title='Report Template Duplicated' if success else 'Report Template Duplication Failed'" in routes
    assert "action_label='View Report Templates'" in routes
