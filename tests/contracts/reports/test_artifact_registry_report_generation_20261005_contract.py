from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_artifact_registry_report_contracts_publish_provider_neutral_scope_and_formats() -> None:
    document = yaml.safe_load(read('app/definitions/catalogs/reports/catalog.yaml'))
    specs = {item['value']: item for item in document['report_types']}

    inventory = specs['artifact_registry_inventory']
    analysis = specs['artifact_registry_analysis']

    assert inventory['family'] == 'inventory'
    assert inventory['default_format'] == 'xlsx'
    assert inventory['allowed_formats'] == ['xlsx', 'csv']
    assert inventory['domain'] == 'artifact_registry'
    assert inventory['source_kind'] == 'artifact_registry'
    assert inventory['scope_asset_type'] == 'registry_integration'
    assert inventory['requires_cluster'] is False

    assert analysis['family'] == 'analytics'
    assert analysis['default_format'] == 'pdf'
    assert analysis['allowed_formats'] == ['pdf', 'xlsx', 'csv']
    assert analysis['domain'] == 'artifact_registry'
    assert analysis['source_kind'] == 'artifact_registry'
    assert analysis['scope_asset_type'] == 'registry_integration'
    assert analysis['requires_cluster'] is False


def test_registry_scope_is_resolved_from_active_integration_identity_not_provider_specific_models() -> None:
    scope = read('app/reports/scope.py')
    generation = read('app/reports/generate/service.py')
    schedules = read('app/reports/schedules/service.py')

    assert "ARTIFACT_REGISTRY_INSTANCE_ASSET_TYPE = 'registry_integration'" in scope
    assert 'IntegrationInstance' in scope
    assert "instance.integration_type != 'registry'" in scope
    assert "'Artifact Registry'" in scope
    assert "'Integration Scope'" in scope

    assert "IntegrationInstance.integration_type == 'registry'" in generation
    assert "'artifact_registries': artifact_registry_options" in generation
    assert "'registry_integration_id':" in generation
    assert 'report.scope_asset_type = report_spec.scope_asset_type' in generation
    assert 'report.scope_asset_id = registry_integration_id' in generation

    assert 'from app.reports.scope import get_active_registry_options as _get_artifact_registry_options' in schedules
    assert 'artifact_registry_options = _get_artifact_registry_options()' in schedules
    assert "'artifact_registries': artifact_registry_options" in schedules
    assert 'schedule.scope_asset_type = spec.scope_asset_type' in schedules
    assert 'schedule.scope_asset_id = instance_id or None' in schedules


def test_generate_and_schedule_ui_switch_to_registry_scope_without_new_workflow_pattern() -> None:
    generate_page = read('app/templates/reports/generate/index.html')
    generate_js = read('app/static/js/reports/generate.js')
    schedule_page = read('app/templates/reports/schedules/index.html')
    schedule_js = read('app/static/js/report_schedules.js')

    assert 'data-report-scope-panel="registry_integration"' in generate_page
    assert 'id="artifact-registry-select"' in generate_page
    assert '"has_artifact_registries"' in generate_page
    assert "scopeType === 'registry_integration'" in generate_js
    assert 'artifactRegistryScope' in generate_js
    assert 'artifactRegistrySelect' in generate_js
    assert 'Integration Scope' in generate_js

    assert 'data-schedule-artifact-registry-scope' in schedule_page
    assert 'data-schedule-artifact-registry' in schedule_page
    assert "scopeAssetType === 'registry_integration'" in schedule_js
    assert 'usesArtifactRegistry' in schedule_js


def test_registry_inventory_export_is_committed_snapshot_only_and_reuses_inventory_engine() -> None:
    payload = read('app/reports/export/payloads/artifact_registry_inventory.py')
    common = read('app/reports/export/inventory_common.py')
    profile = read('app/reports/export/xlsx/profiles_infrastructure.py')

    assert 'RegistryProject.query.options(' in payload
    assert 'RegistryCollectionState' in payload
    assert "'inventory_assets': rows" in payload
    assert "'data_cutoff': cutoff" in payload
    assert 'Harbor' not in payload
    assert 'requests.' not in payload

    assert "report.report_type == 'artifact_registry_inventory'" in common
    assert 'get_report_artifact_registry_inventory_payload' in common
    assert "'artifact_registry_inventory': InventoryWorkbookProfile(" in profile
    assert "row_source='inventory_assets'" in profile
    assert "identity_columns=('registry', 'environment', 'project', 'repository', 'digest')" in profile


def test_registry_analysis_combines_dashboard_alert_intelligence_and_recommendations_without_live_provider_calls() -> (
    None
):
    payload = read('app/reports/export/payloads/artifact_registry_analysis.py')
    collectors = read('app/reports/export/html_pdf/collectors.py')
    builder = read('app/reports/export/html_pdf/builder.py')
    template = read('app/templates/reports/pdf/artifact_registry_analysis.html')
    analytics_profile = read('app/reports/export/xlsx/analytics_profile_catalog.py')
    analytics_map = read('app/reports/export/xlsx/analytics_profiles.py')

    assert 'build_overview(provider_id=instance_id)' in payload
    assert "'artifact_registry_alerts_actions':" in payload
    assert "'recommendations': recommendations" in payload
    assert "'live_provider_requests': 'Excluded during report rendering'" in payload
    assert 'Harbor' not in payload
    assert 'requests.' not in payload

    assert "'artifact_registry_analysis': get_report_artifact_registry_analysis_payload" in collectors
    assert "report.report_type == 'artifact_registry_analysis'" in builder
    assert "template_name = 'reports/pdf/artifact_registry_analysis.html'" in builder
    assert 'Evidence Boundary' in template
    assert 'report generation does not query Harbor' in template

    assert "'artifact_registry_analysis': AnalyticsWorkbookProfile(" in analytics_profile
    assert "'artifact_registry_analysis': prepare_artifact_registry" in analytics_map


def test_registry_reports_are_definition_driven_system_templates_and_visible_in_reports_overview() -> None:
    template_service = read('app/reports/report_templates/service.py')
    overview = read('app/reports/overview/service.py')
    constants = read('app/reports/export/constants.py')

    assert 'for spec in REPORT_TYPE_SPECS' in template_service
    assert 'Kubernetes + Object Storage + Artifact Registry' in template_service
    assert "domain_order = ['kubernetes', 'object_storage', 'artifact_registry', 'server', 'hci']" in overview
    assert "REPORT_DOMAIN_ARTIFACT_REGISTRY = 'artifact_registry'" in constants
    assert "REPORT_DOMAIN_ARTIFACT_REGISTRY: 'KAORI Artifact Registry Reports'" in constants

    # Operational Registry cards read the canonical definition, not the Reports application.
    registry_presentation = read('app/artifact_registry/presentation_common.py')
    assert "load_definition_document('reports/catalog.yaml', expected_kind='report_catalog')" in registry_presentation
    assert "for spec in report_catalog['report_types']" in registry_presentation
    assert 'from app.reports.catalog import' not in registry_presentation
