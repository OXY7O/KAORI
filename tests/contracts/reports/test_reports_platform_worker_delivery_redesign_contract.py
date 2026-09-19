from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
REPORT_TEMPLATES = ROOT / 'app' / 'templates' / 'reports'


def read(path: Path) -> str:
    return path.read_text()


def test_reports_pages_use_standard_heroes_and_compact_summary_strips() -> None:
    for page in ('generated', 'report_templates', 'storage', 'schedules'):
        source = read(REPORT_TEMPLATES / page / 'index.html')
        assert 'page_hero.shell_classes()' in source

    generated = read(REPORT_TEMPLATES / 'generated' / 'index.html')
    assert 'reports/components/_summary_strip.html' not in generated
    assert 'data-generated-report-registry="true"' in generated
    assert 'Generation Posture' in generated

    report_templates = read(REPORT_TEMPLATES / 'report_templates' / 'index.html')
    storage = read(REPORT_TEMPLATES / 'storage' / 'index.html')
    schedules = read(REPORT_TEMPLATES / 'schedules' / 'index.html')
    for source in (report_templates, storage, schedules):
        assert 'reports/components/_summary_strip.html' not in source
    assert 'payload.summary_cards[0]' in report_templates
    assert 'data-report-storage-readiness-monitor="true"' in storage
    assert '{% for card in payload.summary_cards %}' in schedules

    generate = read(REPORT_TEMPLATES / 'generate' / 'index.html')
    generate_runtime = read(ROOT / 'app' / 'static' / 'js' / 'reports' / 'generate.js')
    generate_service = read(ROOT / 'app' / 'reports' / 'generate' / 'service.py')

    assert 'page_hero.shell_classes()' in generate
    assert 'page_hero.layout_classes()' in generate
    assert 'page_hero.content_classes()' in generate
    assert 'page_hero.context_card(' in generate
    assert 'Infrastructure Asset Scope' in generate
    assert 'Catalog-Driven Contract' in generate
    assert 'Queued Artifact Generation' in generate
    assert 'data-generate-report-workspace="wizard"' in generate
    assert 'data-generate-wizard="true"' in generate
    assert 'data-generate-step="report"' in generate
    assert 'data-generate-step="scope"' in generate
    assert 'data-generate-step="artifact"' in generate
    assert 'data-generate-step="summary"' in generate
    assert 'Review & Queue' in generate
    assert 'id="namespace-select"' in generate
    assert 'namespaceOptionsByCluster' in generate_runtime
    assert 'Cluster selection loads namespace options.' not in generate + generate_runtime
    assert 'Select a specific cluster to load namespace options.' not in generate + generate_runtime
    assert 'id="namespace-select-help"' not in generate
    assert 'id="namespace-input"' not in generate
    assert 'id="preview-report-name"' in generate
    assert 'syncPreviewReportName' in generate_runtime
    assert 'Ready to Queue' in generate + generate_runtime
    assert 'Create &amp; Queue Report' in generate
    assert 'Report Type Guide' not in generate
    assert 'Generation Guide' not in generate
    assert 'Storage Context' not in generate
    assert 'Generation Readiness' not in generate
    assert 'Request Preview' not in generate
    assert 'xl:sticky xl:top-5 xl:self-start' not in generate
    assert '{% import "components/info_flow.html" as info_flow %}' not in generate
    assert '{% import "components/related_page_card.html" as related_page_card %}' not in generate
    assert 'border-rose-200' not in generate
    assert 'border-amber-200' not in generate
    assert "'generation_flow': _get_generation_flow()" not in generate_service
    assert "'report_type_guide_groups': _get_report_type_guide_groups()" not in generate_service
    assert "'recommended_actions': _get_recommended_actions()" not in generate_service
    assert "'readiness': _get_generation_readiness(" not in generate_service
    assert "'namespace_options_by_cluster': namespace_options_by_cluster" in generate_service
    preview_name_contract = "'preview_report_name': form_state['name'].strip() or build_default_report_name(form_state)"
    assert preview_name_contract in generate_service
    assert 'def _get_namespace_options_by_cluster()' in generate_service
    assert 'NamespaceInventory.namespace == namespace' in generate_service
    assert 'MVP2' not in generate + generate_runtime


def test_reporting_capability_explains_types_and_readiness() -> None:
    workspace = read(REPORT_TEMPLATES / 'overview' / 'partials' / '_coverage_pipeline_workspace.html')
    coverage = read(REPORT_TEMPLATES / 'overview' / 'partials' / '_report_type_coverage.html')
    pipeline = read(REPORT_TEMPLATES / 'overview' / 'partials' / '_pipeline_status.html')

    assert 'Reporting Capability' in workspace
    assert '\n                    Types\n' in workspace
    assert '\n                    Pipeline\n' in workspace
    assert 'Browse report contracts currently supported by connected and validated data sources.' in workspace
    assert (
        'Follow request creation, format-specific execution, artifact storage, and optional Notification Channel delivery.'
        in workspace
    )
    assert 'output supported by the currently connected and validated data sources' in coverage
    assert 'Canonical flow:' in pipeline
    assert 'scheduled delivery emits a governed report event to the selected Notification Channels' in pipeline
    assert 'text-sm font-semibold leading-5 text-content-primary' in workspace
    assert 'text-xs leading-5 text-content-muted' in workspace
    assert 'Expand one domain at a time' not in workspace + coverage + pipeline


def test_reports_blueprint_and_page_routes_hide_raw_dependency_errors() -> None:
    reports_routes = read(ROOT / 'app' / 'reports' / 'routes.py')
    unavailable = read(REPORT_TEMPLATES / '_unavailable.html')

    assert '@reports_bp.errorhandler(Exception)' in reports_routes
    assert 'handle_reports_exception' in reports_routes
    assert 'render_reports_unavailable(' in reports_routes
    assert 'Raw Error Hidden' in unavailable
    assert 'technical exception in server logs' in unavailable
    assert 'data-reports-recovery-panel="unified"' in unavailable
    assert 'Operational Impact' in unavailable
    assert 'Recommended Checks' in unavailable
    assert 'Retry Storage Check' in unavailable
    assert 'What Happened' not in unavailable
    assert 'Recommended Check</h2>' not in unavailable
    assert 'Traceback' not in unavailable
    assert 'ClientError' not in unavailable

    for route in (
        ROOT / 'app' / 'reports' / 'generated' / 'routes.py',
        ROOT / 'app' / 'reports' / 'generate' / 'routes.py',
        ROOT / 'app' / 'reports' / 'report_templates' / 'routes.py',
        ROOT / 'app' / 'reports' / 'storage' / 'routes.py',
        ROOT / 'app' / 'reports' / 'schedules' / 'routes.py',
    ):
        assert 'render_reports_unavailable' in read(route), route


def test_generated_registry_surfaces_storage_outage_without_breaking_list() -> None:
    service = read(ROOT / 'app' / 'reports' / 'generated' / 'service.py')
    template = read(REPORT_TEMPLATES / 'generated' / 'index.html')
    export_service = read(ROOT / 'app' / 'reports' / 'export' / 'service.py')

    assert "'storage_notice': storage_notice" in service
    assert 'storage_reachable' in service
    assert 'Artifact Storage Needs Review' in template
    assert 'Open Storage' in template
    assert 'Report storage is temporarily unavailable.' in export_service


def test_report_schedule_dispatcher_uses_canonical_worker_job() -> None:
    definition = read(ROOT / 'app' / 'platform_operations' / 'jobs' / 'definitions' / 'report_schedule.py')
    job_catalog = yaml.safe_load(
        read(ROOT / 'app' / 'definitions' / 'catalogs' / 'platform_operations' / 'jobs' / 'registered_jobs.yaml')
    )
    registry = read(ROOT / 'app' / 'platform_operations' / 'jobs' / 'registry.py')
    adapter = read(ROOT / 'app' / 'reports' / 'schedules' / 'job_adapter.py')
    task = read(ROOT / 'app' / 'reports' / 'schedules' / 'tasks.py')
    config = read(ROOT / 'app' / 'config' / 'default.py')
    compose = read(ROOT / 'compose.production.yml')
    dev_compose = read(ROOT / '.devcontainer' / 'compose.devcontainer.yml')
    devcontainer = read(ROOT / '.devcontainer' / 'devcontainer.json')
    queue_contract = read(ROOT / 'app' / 'reports' / 'jobs' / 'queue.py')

    schedule_definition = next(item for item in job_catalog['jobs'] if item['key'] == 'reports.schedule.dispatch')
    assert schedule_definition['queue_name'] == 'reports'
    assert schedule_definition['operation'] == 'dispatch_due_reports'
    assert schedule_definition['dispatcher_path'] == ('app.reports.schedules.job_adapter:dispatch_report_schedule_job')
    assert "get_job_definition('reports.schedule.dispatch')" in definition
    assert '_JOB_DEFINITIONS: tuple[JobDefinition, ...] = load_job_definitions()' in registry
    assert 'enqueue_canonical_job(' in adapter
    assert "name='app.reports.schedules.tasks.run_report_schedule_job'" in task
    assert "'app.reports.schedules.tasks'" in config
    assert "'app.reports.schedules.tasks.run_report_schedule_job'" in config
    assert 'reports-worker:' in compose
    assert 'REPORTS_CELERY_QUEUE:-reports' in compose
    assert '--hostname=reports@%h' in compose
    assert 'reports-worker:' in dev_compose
    assert 'REPORTS_CELERY_QUEUE:-reports' in dev_compose
    assert '--hostname=reports@%h' in dev_compose
    assert '"reports-worker"' in devcontainer
    assert 'get_reports_queue_name()' in adapter
    assert 'REPORTS_CELERY_QUEUE' in queue_contract


def test_report_delivery_uses_platform_notification_channels_by_identity() -> None:
    model = read(ROOT / 'app' / 'models' / 'report.py')
    migration = read(ROOT / 'migrations' / 'versions' / '20260814_report_notification_channels.py')
    delivery = read(ROOT / 'app' / 'reports' / 'notifications.py')
    channel_service = read(ROOT / 'app' / 'integrations' / 'delivery' / 'notification_channels' / 'service.py')
    report_worker = read(ROOT / 'app' / 'reports' / 'jobs' / 'tasks.py')
    schedule_template = read(REPORT_TEMPLATES / 'schedules' / 'index.html')

    assert 'notification_channel_ids' in model
    assert 'notification_channels:' not in model
    assert 'delivery_result' in model
    assert "new_column_name='notification_channel_ids'" in migration
    assert "REPORT_NOTIFICATION_EVENT = 'report.generated'" in delivery
    assert 'dispatch_notification_event(' in delivery
    assert 'def dispatch_notification_event(' in channel_service
    assert 'deliver_generated_report(' in report_worker
    assert 'Timing &amp; Delivery' in schedule_template
    assert 'payload.delivery_channel_options' in schedule_template
    assert 'notification_channel_ids' in schedule_template
    assert 'Manage Notification Channels' in schedule_template
    assert 'run.delivery_label' in schedule_template

    overview_service = read(ROOT / 'app' / 'reports' / 'overview' / 'service.py')
    assert "'name': 'Notification Channels'" in overview_service
    assert 'Telegram, email, and Microsoft Teams channels can be selected per report schedule.' in overview_service


def test_report_user_interfaces_do_not_expose_mvp_copy() -> None:
    paths = [
        *REPORT_TEMPLATES.rglob('*.html'),
        ROOT / 'app' / 'reports' / 'storage' / 'service.py',
        ROOT / 'app' / 'reports' / 'storage' / 'health.py',
    ]
    combined = '\n'.join(read(path) for path in paths)
    assert 'MVP2' not in combined
    assert ' MVP ' not in combined


def test_generate_report_uses_the_canonical_family_format_and_scope_contract() -> None:
    catalog = read(ROOT / 'app' / 'reports' / 'catalog.py')
    catalog_definitions = read(ROOT / 'app' / 'definitions' / 'catalogs' / 'reports' / 'catalog.yaml')
    generate_service = read(ROOT / 'app' / 'reports' / 'generate' / 'service.py')
    generate_form_options = read(ROOT / 'app' / 'reports' / 'generate' / 'form_options.py')
    generate_template = read(REPORT_TEMPLATES / 'generate' / 'index.html')
    generate_runtime = read(ROOT / 'app' / 'static' / 'js' / 'reports' / 'generate.js')
    analytics_collectors = read(ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'collectors.py')
    inventory_common = read(ROOT / 'app' / 'reports' / 'export' / 'inventory_common.py')
    artifact_registry = read(ROOT / 'app' / 'reports' / 'export' / 'artifacts.py')
    inventory_payload = read(ROOT / 'app' / 'reports' / 'export' / 'payloads' / 'inventory.py')
    template_service = read(ROOT / 'app' / 'reports' / 'report_templates' / 'service.py')

    inventory_report_types = (
        'inventory_overview',
        'node_inventory',
        'namespace_inventory',
        'workload_inventory',
        'pod_inventory',
        'service_inventory',
        'ingress_inventory',
        'configuration_inventory',
        'storage_inventory',
        'tls_inventory',
    )

    for report_type in inventory_report_types:
        assert f'- value: {report_type}' in catalog_definitions

    assert '- value: object_storage_inventory' in catalog_definitions
    assert '- value: object_storage_analysis' in catalog_definitions
    assert 'allowed_formats:' in catalog_definitions
    assert '- pdf' in catalog_definitions and '- csv' in catalog_definitions
    assert '- xlsx' in catalog_definitions
    assert 'requires_cluster: bool = True' in catalog
    assert 'Cross-cluster report generation is disabled.' in catalog

    assert 'FORMAT_PDF: render_weasyprint_pdf' in artifact_registry
    assert 'FORMAT_XLSX: render_report_xlsx' in artifact_registry
    assert 'FORMAT_CSV: render_report_csv' in artifact_registry
    assert 'get_report_kubernetes_inventory_payload' not in analytics_collectors
    assert 'def collect_inventory_payload' in inventory_common
    assert 'def get_inventory_rows' in inventory_common
    assert 'filter_current_generation(query, model)' in inventory_payload
    assert 'query = query.filter(model.cluster_id == cluster_id)' in inventory_payload

    assert 'payload.report_type_groups' in generate_template
    assert 'data-report-contract-group="{{ group.key }}"' in generate_template
    assert "'report_type_groups': _get_report_type_groups()" in generate_service
    assert 'def _get_report_type_groups()' in generate_service
    assert "('kubernetes', 'Kubernetes')" not in generate_template
    assert "('object_storage', 'Object Storage')" not in generate_template
    assert 'data-report-family-filter=' not in generate_template
    assert 'data-report-type-card=' not in generate_template
    assert "'value': 'snapshot'" in generate_form_options
    assert 'A selected Kubernetes cluster is required for this report artifact.' in generate_service
    assert 'A selected Object Storage system is required for this report artifact.' in generate_service
    assert "reportType.family === 'inventory'" in generate_runtime
    assert 'allowed_formats' in generate_template
    assert 'Artifact Storage Needs Review' in generate_template
    assert 'Output Format' in generate_template
    assert 'get_report_type_spec(report_type).family == REPORT_FAMILY_INVENTORY' in template_service


def test_report_export_packages_keep_renderer_imports_lazy() -> None:
    package_contracts = (
        (
            ROOT / 'app' / 'reports' / 'export' / 'xlsx' / '__init__.py',
            'app.reports.export.xlsx.renderer',
            'render_inventory_xlsx',
        ),
        (
            ROOT / 'app' / 'reports' / 'export' / 'csv' / '__init__.py',
            'app.reports.export.csv.renderer',
            'render_report_csv',
        ),
    )

    for path, renderer_module, public_function in package_contracts:
        module = ast.parse(path.read_text())
        eager_imports = {node.module for node in module.body if isinstance(node, ast.ImportFrom)}
        assert renderer_module not in eager_imports

        wrapper = next(
            node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == public_function
        )
        lazy_imports = {node.module for node in ast.walk(wrapper) if isinstance(node, ast.ImportFrom)}
        assert renderer_module in lazy_imports
