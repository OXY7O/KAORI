from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_job_configuration_does_not_inspect_queue_activity_on_initial_render() -> None:
    routes = _read('app/platform_operations/jobs/routes.py')

    assert "if active_section == 'configuration':" in routes
    assert 'build_job_configuration_summary_context' in routes
    assert "tab_override=fragment if fragment in {'active', 'registry', 'queues'} else None" in routes
    assert 'include_queue_activity' not in routes


def test_inventory_manual_dispatch_uses_activity_center_without_progress_toast() -> None:
    routes = _read('app/platform_operations/jobs/routes.py')
    workspace = _read('app/templates/platform_operations/jobs/configuration/_job_workspace.html')

    assert 'sync_progress' not in routes
    assert 'sync_progress' not in workspace
    assert '_quick_sync_status.html' not in workspace
    assert 'operation_feedback_oob.html' in workspace


def test_job_configuration_copy_is_compact_and_planned_catalog_is_removed() -> None:
    workspace = _read('app/templates/platform_operations/jobs/configuration/_workspace.html')
    materialization = _read(
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html'
    )

    assert 'Centralized orchestration with domain-owned execution.' in workspace
    assert 'Job orchestration is centralized here while execution logic remains in its owning domain.' not in workspace
    assert 'Planned Job Definitions' not in workspace
    assert 'Keep the last successful result available.' in materialization
    assert 'Serve the last successful result during refresh or source failure.' not in materialization


def test_policy_timeline_and_delivery_channel_cards_use_clear_surfaces() -> None:
    for relative in (
        'app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/tls_certificate_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html',
    ):
        source = _read(relative)
        assert 'overflow-hidden rounded-xl border border-outline-subtle bg-surface-card' in source

    report = _read('app/templates/platform_operations/jobs/configuration/definitions/report_schedule.html')
    assert 'article class="rounded-xl border border-outline-subtle bg-surface-card p-4"' in report
    assert 'article class="rounded-xl border border-outline-subtle bg-surface-hover p-4"' not in report
