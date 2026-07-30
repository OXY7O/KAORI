from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT_TEMPLATES = ROOT / 'app' / 'templates' / 'reports'


def read(path: Path) -> str:
    return path.read_text()


def test_reports_pages_use_standard_heroes_and_compact_summary_strips() -> None:
    for page in ('generated', 'report_templates', 'storage', 'schedules'):
        source = read(REPORT_TEMPLATES / page / 'index.html')
        assert 'page_hero.shell_classes()' in source
        assert 'reports/components/_summary_strip.html' in source

    generate = read(REPORT_TEMPLATES / 'generate' / 'index.html')
    generate_service = read(ROOT / 'app' / 'reports' / 'generate' / 'service.py')

    assert 'Generation Readiness' in generate
    assert 'Generation Guide' in generate
    assert 'Follow the governed request-to-artifact flow.' in generate
    assert 'Storage Context' in generate
    assert 'Request Preview' in generate
    assert 'Create Report Request' in generate
    assert 'Report Type Guide' in generate
    assert 'xl:sticky xl:top-5 xl:self-start' in generate
    assert 'x-collapse' not in generate
    assert 'Data Source Context' not in generate
    assert 'Report Output Readiness' not in generate
    assert 'Create report request' not in generate
    assert 'Specific cluster required' not in generate
    assert 'Select all' not in generate
    assert 'Reset default' not in generate
    assert 'rounded-full' not in generate
    assert "'generation_flow': _get_generation_flow()" in generate_service
    assert "'data_source_context'" not in generate_service
    assert "'report_output_readiness'" not in generate_service
    assert 'def _get_data_source_context' not in generate_service
    assert 'def _get_report_output_readiness' not in generate_service
    assert 'MVP2' not in generate


def test_reporting_capability_explains_types_and_readiness() -> None:
    workspace = read(REPORT_TEMPLATES / 'overview' / 'partials' / '_coverage_pipeline_workspace.html')
    coverage = read(REPORT_TEMPLATES / 'overview' / 'partials' / '_report_type_coverage.html')
    pipeline = read(REPORT_TEMPLATES / 'overview' / 'partials' / '_pipeline_status.html')

    assert 'Reporting Capability' in workspace
    assert '\n                    Types\n' in workspace
    assert '\n                    Pipeline\n' in workspace
    assert 'Browse report contracts currently supported by connected and validated data sources.' in workspace
    assert 'Follow request creation, PDF execution, artifact storage, and optional Telegram delivery.' in workspace
    assert 'output supported by the currently connected and validated data sources' in coverage
    assert 'Manual flow:' in pipeline
    assert 'Scheduled flow:' in pipeline
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
    assert 'Review Storage' in template
    assert 'Report storage is temporarily unavailable.' in export_service


def test_report_schedule_dispatcher_uses_canonical_worker_job() -> None:
    definition = read(ROOT / 'app' / 'jobs' / 'definitions' / 'report_schedule.py')
    registry = read(ROOT / 'app' / 'jobs' / 'registry.py')
    adapter = read(ROOT / 'app' / 'reports' / 'schedules' / 'job_adapter.py')
    task = read(ROOT / 'app' / 'reports' / 'schedules' / 'tasks.py')
    config = read(ROOT / 'app' / 'config' / 'default.py')
    compose = read(ROOT / 'compose.production.yml')

    assert "key='reports.schedule.dispatch'" in definition
    assert "queue_name='reports'" in definition
    assert 'REPORT_SCHEDULE_DEFINITION' in registry
    assert 'enqueue_canonical_job(' in adapter
    assert "name='app.reports.schedules.tasks.run_report_schedule_job'" in task
    assert "'app.reports.schedules.tasks'" in config
    assert "'app.reports.schedules.tasks.run_report_schedule_job'" in config
    assert 'reports-worker:' in compose
    assert 'REPORTS_CELERY_QUEUE:-reports' in compose


def test_report_delivery_is_telegram_first_and_channel_extensible() -> None:
    model = read(ROOT / 'app' / 'models' / 'report.py')
    migration = read(ROOT / 'migrations' / 'versions' / '20260729_report_schedule_delivery_channels.py')
    delivery = read(ROOT / 'app' / 'reports' / 'delivery' / 'service.py')
    telegram = read(ROOT / 'app' / 'reports' / 'delivery' / 'telegram.py')
    schedule_service = read(ROOT / 'app' / 'reports' / 'schedules' / 'service.py')
    schedule_template = read(REPORT_TEMPLATES / 'schedules' / 'index.html')

    assert 'notification_channels' in model
    assert 'delivery_result' in model
    assert "op.add_column(\n        'report_schedules'" in migration
    for channel in ('telegram', 'email', 'slack', 'webhook'):
        assert f"'value': '{channel}'" in delivery
    assert "_CHANNELS: dict[str, ReportDeliveryChannel] = {'telegram': TelegramReportDelivery()}" in delivery
    assert 'api.telegram.org' in telegram
    assert 'deliver_generated_report(' in schedule_service
    assert 'Delivery Channels' in schedule_template
    assert 'notification_channels' in schedule_template
    assert 'Delivery:' in schedule_template

    overview_service = read(ROOT / 'app' / 'reports' / 'overview' / 'service.py')
    assert "'name': 'Telegram'" in overview_service
    assert "'status': 'Telegram Ready' if telegram_ready else 'Telegram Setup Required'" in overview_service
    assert 'Email, webhook, and notification delivery remain planned' not in overview_service


def test_report_user_interfaces_do_not_expose_mvp_copy() -> None:
    paths = [
        *REPORT_TEMPLATES.rglob('*.html'),
        ROOT / 'app' / 'reports' / 'storage' / 'service.py',
        ROOT / 'app' / 'reports' / 'storage' / 'health.py',
    ]
    combined = '\n'.join(read(path) for path in paths)
    assert 'MVP2' not in combined
    assert ' MVP ' not in combined
