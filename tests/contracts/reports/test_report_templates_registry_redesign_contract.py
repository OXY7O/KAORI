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
    assert "marker_name='data-template-filters'" in template
    assert "marker_value='true'" in template
    assert 'xl:grid-cols-7' not in template
    assert 'Template Registry' in template
    assert '>Template<' in template
    assert '>Domain<' in template
    assert '>Family<' in template
    assert '>Report Type<' in template
    assert '>Output<' in template
    assert '>Sections<' in template
    assert '>Ownership<' in template
    assert '>Action<' in template
    assert 'components/loading_bar.html' in template
    assert (
        "loading_bar.render('templates-registry-loading', active=false, label='Refreshing Template Registry')"
        in template
    )
    assert 'data-kaori-template-loading-region="true"' in template
    assert 'components/table_registry.html' in template
    assert 'registry_ui.filter_form(' in template
    assert 'registry_ui.footer(' in template
    assert 'registry_ui.clear_filters_link(' in template
    assert 'data-template-page-size-form="true"' not in template
    assert 'data-kaori-page-size-control="report-templates"' not in template
    assert 'id="templates-registry-request-scope"' not in template
    assert 'hx-trigger="change, input delay:450ms"' not in template
    assert 'from:select' not in template
    assert 'from:input' not in template
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
    apply_state = service.split('def apply_template_state(', 1)[1].split('def apply_template_owner_snapshot(', 1)[0]
    assert 'template.source_template_key = f\'system:{form_state["report_type"]}\'' in apply_state
    assert "'domains': [" in service
    assert "'families': [" in service
    assert "'ownership': [" in service
    assert "'formats': [" in service
    assert "'domain': args.get('domain', '').strip()" in service
    assert "'search': args.get('search', '').strip()" in service
    assert "'System Template'" in service
    assert "'system_count': system_count" in service
    assert "'custom_count': custom_count" in service
    assert "'active_custom_count': active_custom_count" in service
    assert "'Active Custom'" in service
    assert "'protected_coverage_percent': protected_coverage_percent" in service
    assert "'supported_formats_label': ' · '.join(supported_formats)" in service
    assert 'from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window' in service
    assert 'def normalize_templates_per_page' not in service
    assert 'def build_templates_page_window' not in service
    assert 'def build_templates_page_href' not in service
    assert 'def parse_positive_int' not in service
    assert 'pagination = build_pagination_window(' in service
    assert "'per_page_options': list(PER_PAGE_OPTIONS)" in service
    assert "'can_generate': contract_valid and status == 'active'" in service
    assert "'registry_return_url': registry_return_url" in service
    assert 'build_template_registry_url(' in service


def test_template_feedback_titles_follow_title_case() -> None:
    routes = read(ROUTES)

    assert "title='Report Template Validation Failed'" in routes
    assert "title='Report Template Created'" in routes
    assert "title='Report Template Updated'" in routes
    assert "title='Report Template Deleted' if success else 'Report Template Deletion Failed'" in routes
    assert "title='Report Template Duplicated' if success else 'Report Template Duplication Failed'" in routes
    assert "action_label='View Report Templates'" in routes


def test_template_mutations_preserve_registry_context() -> None:
    routes = read(ROUTES)
    template = read(TEMPLATE)

    assert 'safe_next_url' in routes
    assert 'def _template_registry_return_url(' in routes
    assert 'def _template_edit_url(' in routes
    assert "request.form.get('next')" in routes
    assert routes.count('registry_return_url=registry_return_url') >= 4
    assert 'name="next" value="{{ payload.registry_return_url }}"' in template
    assert template.count('name="next" value="{{ payload.registry_return_url }}"') >= 4
    assert 'Activate to Generate' in template


def test_template_registry_uses_shared_table_geometry_and_keeps_contract_columns() -> None:
    from jinja2 import Environment

    template = read(ROOT / 'app/templates/reports/report_templates/index.html')
    Environment().parse(template)
    registry = template.split('data-template-registry-table="compact-v3"', 1)
    assert len(registry) == 2
    prefix = registry[0].rsplit('<div class="min-w-0 overflow-x-auto">', 1)[1]
    assert "table_ui.table_classes('min-w-[1050px] !table-fixed')" in prefix
    table = registry[1].split('</table>', 1)[0]
    assert '<caption class="sr-only">' in table
    assert 'table_ui.head_classes()' in table
    assert 'table_ui.body_classes()' in table
    assert 'table_ui.row_classes()' in table
    assert table.count('scope="col"') == 6
    assert table.count('table_ui.header_cell_classes(') == 6
    assert table.count('table_ui.cell_classes(') == 6
    for proportion in ('31', '25', '12', '10', '14', '8'):
        assert f'w-[{proportion}%]' in table
    assert 'data-template-row="{{ template.template_key }}"' in table
    assert 'table_label.status_indicator_label(template.status_label, template.status_tone)' in table
    assert 'data-dialog-target="template-detail-{{ loop.index }}"' in table
    assert '<thead class="border-b border-outline-subtle' not in table
    assert '<td class="px-4 py-4 align-top"' not in table


def test_template_registry_filter_fields_compose_canonical_controls() -> None:
    from jinja2 import Environment

    template = read(ROOT / 'app/templates/reports/report_templates/index.html')
    Environment().parse(template)
    region = template.split('{% call registry_ui.filter_form(', 1)[1].split('{% endcall %}', 1)[0]
    assert "marker_name='data-template-filters'" in region
    assert region.count('table_ui.filter_select_classes()') == 6
    assert region.count('table_ui.filter_input_classes()') == 1
    assert region.count('table_ui.filter_label_classes()') == 7
    for field in ('search', 'family', 'domain', 'report_type', 'ownership', 'status', 'output_format'):
        assert f'name="{field}"' in region
    assert 'payload.selected_filters.search' in region
    assert 'payload.selected_filters.output_format' in region
    assert 'min-h-9 w-full rounded-lg' not in region
    assert 'relative mt-1.5' not in region
    assert 'Search Templates...' in region


def test_template_action_groups_use_shared_semantic_button_variants() -> None:
    from jinja2 import Environment

    template = read(ROOT / 'app/templates/reports/report_templates/index.html')
    Environment().parse(template)
    assert '{% import "components/action_button.html" as action_button %}' in template
    assert template.count("action_button.classes('primary')") == 3
    assert template.count("action_button.classes('critical')") == 1
    assert template.count("action_button.classes('secondary')") == 1

    for token in ('data-operation-submit', 'data-loading-label="Creating Custom Template..."',
                  'data-loading-label="Deleting Template..."', 'data-dialog-target="template-form-dialog"',
                  'data-dialog-target="template-delete-{{ loop.index }}"',
                  'data-kaori-dialog-close', 'csrf_token', 'template.delete_href',
                  'template.duplicate_href', 'template.edit_href'):
        assert token in template
    assert "table_ui.action_classes()" in template
    assert 'data-template-registry-table="compact-v3"' in template
    assert '<i data-lucide="arrow-up-right" class="h-4 w-4" aria-hidden="true"></i>' in template
    assert 'inline-flex min-h-9 items-center justify-center gap-2 rounded-lg bg-kaori-primary' not in template
    assert 'bg-status-critical-soft px-4 text-xs font-semibold text-status-critical-text' not in template
