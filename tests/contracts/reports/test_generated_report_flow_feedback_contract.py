from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_generate_redirects_to_focused_registry_with_immediate_queue_toast() -> None:
    route = read(ROOT / 'app/reports/generate/routes.py')

    assert "generated_url = url_for('reports.generated_reports', focus=report.id, period='all')" in route
    assert "title='Report Queued'" in route
    assert "'feedback_delivery': 'toast'" in route
    assert 'delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY' in route
    assert "action_label='Open generated reports'" in route
    assert 'return redirect(generated_url)' in route

    assert "event_type='report_generation_queue_failed'" in route
    assert 'delivery_policy=OperationalDeliveryPolicy.DECK_ON_FAILURE' in route
    assert "title='Report Not Queued'" in route


def test_terminal_report_outcomes_are_persistent_notification_center_events() -> None:
    task = read(ROOT / 'app/reports/jobs/tasks.py')

    assert "event_type='report_generation_completed' if success else 'report_generation_failed'" in task
    assert "'feedback_delivery': 'activity_center'" in task
    assert 'delivery_policy=OperationalDeliveryPolicy.PERSISTENT' in task
    assert "title = 'Report Ready' if success else 'Report Generation Failed'" in task
    assert "'report_name': report.name" in task
    assert "action_label='Open report'" in task


def test_report_events_are_platform_operations_in_notification_center() -> None:
    catalog = read(ROOT / 'app/notifications/event_catalog.py')
    queries = read(ROOT / 'app/notifications/queries.py')

    for prefix in ("'report_'", "'generated_report_'", "'generated_reports_'"):
        assert prefix in catalog

    assert "Notification.event_type.like('report_%')" in queries
    assert "Notification.event_type.like('generated_report_%')" in queries
    assert "Notification.event_type.like('generated_reports_%')" in queries
    assert "target_type='Report'" in catalog
    assert "source_label='Reports operation'" in catalog


def test_generated_registry_is_compact_focused_and_auto_refreshes_pending_work() -> None:
    service = read(ROOT / 'app/reports/generated/service.py')
    template = read(ROOT / 'app/templates/reports/generated/index.html')

    assert "PENDING_STATUSES = [\n    'requested',\n    'queued',\n    'generating',\n]" in service
    assert "'focus': query_args.get(" in service
    assert "'output_format': query_args.get(" in service
    assert "item['is_focused']" in service
    assert "'has_pending_reports': has_pending_reports" in service
    assert "'poll_interval_seconds': 8" in service

    assert 'data-generated-report-registry="true"' in template
    assert 'data-generated-registry-table="true"' in template
    assert 'data-focused-report="true"' in template
    assert 'Live Updates' in template
    assert 'hx-trigger="every {{ payload.poll_interval_seconds }}s"' in template
    polling_block = template.split('hx-trigger="every {{ payload.poll_interval_seconds }}s"', 1)[1].split('{% endif %}', 1)[0]
    assert 'hx-indicator="#generated-report-loading"' not in polling_block
    assert 'data-generated-registry-posture="true"' in template
    assert 'Generated Reporting Posture' in template
    assert 'Total Reports' in template
    assert 'Ready' in template
    assert 'In Progress' in template
    assert 'Needs Review' in template
    assert 'active generation refreshes silently' in template
    assert 'xl:grid-cols-6' in template
    assert 'xl:grid-cols-[minmax(13rem,1.4fr)' not in template
    assert '>Previous<' in template or 'Previous\n' in template
    assert '>Next<' in template or 'Next\n' in template
    assert 'pagination_ui.navigation_classes(false)' in template
    assert 'pagination_ui.navigation_classes(true)' in template
    assert 'table_label.status_indicator_label(report.status' in template
    assert '>Report</th>' in template
    assert '>Scope</th>' in template
    assert '>Artifact</th>' in template
    assert '>Status</th>' in template
    assert '>Updated</th>' in template
    assert '>Action</th>' in template
    assert 'data-generated-report-identity="true"' in template
    assert 'data-generated-report-icon="{{ report.report_icon }}"' in template
    assert 'data-lucide="{{ report.report_icon }}"' in template
    assert 'View more' not in template
    assert 'Report Lifecycle' not in template
    assert 'Storage Context' not in template
    assert 'reports/components/_summary_strip.html' not in template
    assert 'id="generated-report-registry-request-scope"' in template
    assert 'hx-sync="#generated-report-registry-request-scope:abort"' in template
    assert template.count('hx-sync="#generated-report-registry-request-scope:replace"') >= 3
    assert 'data-kaori-page-size-control="generated-reports"' in template
    assert 'hx-trigger="change from:select"' in template
    assert 'GENERATED_PER_PAGE_OPTIONS = (5, 10, 25, 50)' in service
    assert 'def normalize_generated_per_page(value: str | int | None) -> int:' in service
    assert "'per_page': str(normalize_generated_per_page(query_args.get('per_page')))" in service
    assert 'total_pages = max((total_items + per_page - 1) // per_page, 1)' in service
    assert 'page = min(page, total_pages)' in service


def test_generated_registry_keeps_storage_outage_as_degraded_not_blocking() -> None:
    template = read(ROOT / 'app/templates/reports/generated/index.html')
    service = read(ROOT / 'app/reports/generated/service.py')

    assert 'data-generated-storage-degraded="true"' in template
    assert 'Artifact Storage Needs Review' in template
    assert 'Open Storage' in template
    assert "'storage_notice': storage_notice" in service
    assert 'Report records remain available; download actions stay paused' in service
