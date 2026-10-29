"""Data Lifecycle Notification Delivery and Runtime coverage visual contracts (#2959).

Source/Jinja checks do not substitute for disposable PostgreSQL/worker,
Archive Storage checksum or browser/human acceptance.
"""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
UI = 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html'
PRESENTATION = 'app/platform_operations/data_lifecycle/retention/presentation.py'
COVERAGE = 'app/platform_operations/data_lifecycle/retention/domain_coverage.py'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_delivery_notice_is_one_accessible_inline_row_with_violet_and_warning_emphasis() -> None:
    ui = read(UI)
    Environment().parse(ui)
    notice = ui.split("{% if selected.name == 'notification_delivery' %}\n            <p", 1)[1]
    notice = notice.split('</p>', 1)[0]
    assert 'role="note"' in notice
    assert 'text-xs leading-5' in notice
    assert 'text-kaori-primary dark:text-kaori-accent' in notice
    assert 'text-status-warning-text' in notice
    assert '>Archive Only</span>' in notice
    assert '>Cleanup blocked</span>' in notice
    assert 'Hot delivery records retain deduplication, retries, dependencies and lifetime counts.' in notice
    assert 'No per-record archive search.' in notice
    assert '<div' not in notice
    assert 'whitespace-nowrap' not in notice
    assert 'hx-target="#data-lifecycle-domain-workspace"' in ui
    # This domain has no scheduled execution; the UI must not offer dead controls.
    assert "{% if selected.name not in ('notification_delivery', 'audit_event') %}" in ui
    assert "selected.name in ('notification_delivery', 'audit_event') else 'Automatic Run'" in ui
    assert 'Manual Archive Only · No schedule' in ui
    assert "selected.name in ('notification_delivery', 'audit_event')" in ui
    assert 'Source-owned records covered by manual, non-destructive archival.' in ui
    assert 'name="mode" value="archive_only"' in ui
    assert "selected.name not in ('notification_delivery', 'audit_event')" in ui


def test_four_runtime_coverage_sources_are_compact_and_balanced_in_two_columns() -> None:
    ui = read(UI)
    presentation = read(PRESENTATION)
    coverage = read(COVERAGE)
    assert 'from app.platform_operations.data_lifecycle.retention.domain_coverage import _domain_coverage' in presentation
    assert '_domain_coverage(name)' in presentation
    assert 'sm:grid-cols-2' in ui
    assert 'lifecycle.coverage|length == 3' in ui
    assert "selected.name not in ('alert_incident', 'runtime_observation')" not in ui
    assert 'xl:grid-cols-3' in ui  # Other eligible domains preserve existing layout.
    assert 'class="h-full rounded-lg border border-outline-subtle' in ui
    assert '{% for item in lifecycle.coverage %}' in ui
    assert 'bg-surface-subtle' in ui

    runtime = coverage.split("'runtime_observation': (", 1)[1].split('\n        ),', 1)[0]
    for label, description in (
        ('Kubernetes', 'Recent Kubernetes runtime observations.'),
        ('Metrics Source', 'Recent Metrics Source observations.'),
        ('Alertmanager', 'Recent Alertmanager runtime observations.'),
        ('Object Storage · MinIO', 'Recent MinIO storage observations.'),
    ):
        assert f"'label': '{label}'" in runtime
        assert f"'description': '{description}'" in runtime
    assert runtime.count("'label':") == 4


def test_short_domain_labels_preserve_provider_and_retention_safety_truth() -> None:
    presentation = read(PRESENTATION)
    assert 'Kubernetes, Object Storage, Metrics Source and Alertmanager evidence.' in presentation
    assert 'Provider-neutral delivery evidence; manual Archive Only.' in presentation
    assert (
        'Manual Archive Only; paused by default. Hot records retain deduplication, '
        'channel dependencies and lifetime counts; scheduling and cleanup blocked.'
    ) in presentation
    assert 'per-record archive search are excluded' in presentation

    adapter = read('app/platform_operations/data_lifecycle/retention/domains/notification_delivery.py')
    engine = read('app/platform_operations/data_lifecycle/retention/service.py')
    tasks = read('app/platform_operations/data_lifecycle/retention/tasks.py')
    assert 'cleanup_supported = False' in adapter
    assert 'enabled=False' in adapter
    assert "NotificationDelivery.status.in_(('sent', 'skipped'))" in adapter
    assert 'row.payload_json' not in adapter.split('def iter_records(', 1)[1]
    assert "stored_policy.operation_mode != 'archive_only'" in engine
    assert "if domain_name == 'notification_delivery' and not dry_run:" in engine
    assert "if domain_name in {'audit_event', 'notification_delivery'}:" in tasks
