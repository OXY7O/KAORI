from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_report_contracts_are_published_with_canonical_format_policy() -> None:
    document = yaml.safe_load(read('app/definitions/catalogs/reports/catalog.yaml'))
    specs = {item['value']: item for item in document['report_types']}

    inventory = specs['object_storage_inventory']
    analysis = specs['object_storage_analysis']

    assert inventory['family'] == 'inventory'
    assert inventory['default_format'] == 'xlsx'
    assert inventory['allowed_formats'] == ['xlsx', 'csv']
    assert inventory['domain'] == 'object_storage'
    assert inventory['scope_asset_type'] == 'object_storage_system'
    assert inventory['requires_cluster'] is False

    assert analysis['family'] == 'analytics'
    assert analysis['default_format'] == 'pdf'
    assert analysis['allowed_formats'] == ['pdf', 'csv']
    assert analysis['domain'] == 'object_storage'
    assert analysis['scope_asset_type'] == 'object_storage_system'
    assert analysis['requires_cluster'] is False


def test_report_and_schedule_models_persist_generic_asset_scope_with_backfill_migration() -> None:
    model = read('app/models/report.py')
    migration = read('migrations/versions/20260815_report_generic_asset_scope.py')
    scope = read('app/reports/scope.py')

    assert model.count('scope_asset_type: Mapped[str | None]') == 2
    assert model.count('scope_asset_id: Mapped[str | None]') == 2
    assert model.count('scope_asset_label_snapshot: Mapped[str | None]') == 2
    assert "_add_scope_columns('reports')" in migration
    assert "_add_scope_columns('report_schedules')" in migration
    assert "scope_asset_type='kubernetes_cluster'" in migration
    assert "down_revision = '20260814_obj_storage_rbac'" in migration
    assert 'OBJECT_STORAGE_SYSTEM_ASSET_TYPE' in scope
    assert 'resolve_report_scope' in scope


def test_generate_uses_dynamic_infrastructure_asset_scope_for_kubernetes_and_object_storage() -> None:
    service = read('app/reports/generate/service.py')
    page = read('app/templates/reports/generate/index.html')

    assert 'ObjectStorageSystem' in service
    assert "'object_storage_systems': object_storage_system_options" in service
    assert "'object_storage_system_id':" in service
    assert 'report.scope_asset_type = report_spec.scope_asset_type' in service
    assert 'report.scope_asset_id = object_storage_system_id' in service
    assert 'Infrastructure Scope' in page
    assert 'data-report-scope-panel="kubernetes_cluster"' in page
    assert 'data-report-scope-panel="object_storage_system"' in page
    assert 'id="object-storage-system-select"' in page
    assert 'payload.report_type_groups' in page
    assert 'Selected Output Contract' in page
    assert 'XLSX preserves the governed workbook structure' in page
    assert 'PDF preserves the governed analytical document' in page


def test_object_storage_inventory_export_reads_committed_snapshot_and_supports_xlsx_csv() -> None:
    payload = read('app/reports/export/payloads/object_storage_inventory.py')
    common = read('app/reports/export/inventory_common.py')
    xlsx = read('app/reports/export/xlsx/standard.py')

    assert 'ObjectStorageSystem.query.options(selectinload(ObjectStorageSystem.buckets))' in payload
    assert 'provider API calls' in payload
    assert "'inventory_assets': rows" in payload
    assert "report.report_type == 'object_storage_inventory'" in common
    assert "'object_storage_inventory': InventoryWorkbookProfile(" in xlsx
    assert "row_source='inventory_assets'" in xlsx
    assert "column('size_bytes', 'Usage Bytes'" in xlsx
    assert "column('quota_bytes', 'Quota Bytes'" in xlsx


def test_object_storage_analysis_combines_governed_evidence_for_pdf_and_csv() -> None:
    collector = read('app/reports/export/payloads/object_storage_analysis.py')
    collectors = read('app/reports/export/html_pdf/collectors.py')
    builder = read('app/reports/export/html_pdf/builder.py')
    template = read('app/templates/reports/pdf/object_storage_analysis.html')
    csv_renderer = read('app/reports/export/csv/renderer.py')

    assert "get_object_storage_analytics_context('overview', args)" in collector
    assert "get_object_storage_analytics_context('performance', args)" in collector
    assert "get_object_storage_analytics_context('alerts', args)" in collector
    assert "'evidence_boundary': evidence_boundary" in collector
    assert "'object_storage_analysis': get_report_object_storage_analysis_payload" in collectors
    assert "report.report_type == 'object_storage_analysis'" in builder
    assert "template_name = 'reports/pdf/object_storage_analysis.html'" in builder
    assert 'Object Storage System' in template
    assert 'Evidence Boundary' in template
    assert 'build_report_document(' in csv_renderer


def test_jobs_storage_naming_schedules_templates_and_generated_views_use_generic_scope() -> None:
    job_contract = read('app/reports/jobs/contract.py')
    job_service = read('app/reports/jobs/service.py')
    naming = read('app/reports/storage/naming.py')
    schedule_service = read('app/reports/schedules/service.py')
    schedule_page = read('app/templates/reports/schedules/index.html')
    schedule_js = read('app/static/js/report_schedules.js')
    template_service = read('app/reports/report_templates/service.py')
    generated_service = read('app/reports/generated/service.py')
    generated_detail = read('app/templates/reports/generated/detail.html')

    assert 'scope_asset_type: str' in job_contract
    assert 'scope_asset_id: str' in job_contract
    assert 'resolve_report_scope(report)' in job_contract
    assert "scope_type=parameters.scope_asset_type" in job_service
    assert "scope_key=parameters.scope_asset_id" in job_service
    assert 'def get_report_scope_slug' in naming
    assert 'resolve_report_scope(report)' in naming

    assert 'schedule.scope_asset_type = spec.scope_asset_type' in schedule_service
    assert 'schedule.scope_asset_id = system_id or None' in schedule_service
    assert 'report.scope_asset_type = schedule.scope_asset_type' in schedule_service
    assert 'object_storage_systems' in schedule_service
    assert 'data-schedule-object-storage-scope' in schedule_page
    assert 'data-schedule-scope-by-type' in schedule_page
    assert 'scopeByType' in schedule_js
    assert 'domainByType' in schedule_js

    assert "'report_domain': spec.domain" in template_service
    assert 'template.report_domain = spec.domain' in template_service
    assert 'resolve_report_scope(report)' in generated_service
    assert "'scope_label': scope_label" in generated_service
    assert 'payload.report.scope_label' in generated_detail
    assert 'payload.report.scope' in generated_detail


def test_reports_overview_promotes_object_storage_to_published_without_losing_remaining_candidates() -> None:
    coverage = yaml.safe_load(read('app/definitions/catalogs/reports/coverage.yaml'))
    service = read('app/reports/overview/service.py')
    verifier = read('scripts/verify_definition_registry.py')

    object_storage = next(item for item in coverage['domains'] if item['key'] == 'object_storage')
    assert object_storage['status'] == 'Published'
    assert len(object_storage['items']) == 3
    assert {item['name'] for item in object_storage['items']} == {
        'Object Storage Forecast Report',
        'Object Storage Top Consumers Report',
        'Object Storage Alerts & Anomalies Report',
    }
    assert "published_by_domain" in service
    assert "domain_order = ['kubernetes', 'object_storage', 'server', 'hci']" in service
    assert "'published_count': len(published_items)" in service
    assert "Object Storage report coverage must be Published" in verifier
