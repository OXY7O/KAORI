from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_data_lifecycle_tab_order_and_copy_are_compact_and_operational() -> None:
    index = read('app/templates/platform_operations/data_lifecycle/index.html')
    presentation = read('app/retention/presentation.py')

    assert 'framed_workspace_tabs.render([' in index
    tab_tokens = (
        "('policies', 'Retention Policies', 'sliders-horizontal')",
        "('history', 'Archive History', 'history')",
        "('storage', 'Archive Storage', 'hard-drive')",
    )
    for token in tab_tokens:
        assert token in index
    assert index.index(tab_tokens[0]) < index.index(tab_tokens[1]) < index.index(tab_tokens[2])
    assert "tabs: ['policies', 'history', 'storage']" in index
    assert (
        index.index('data-lifecycle-panel-policies')
        < index.index('data-lifecycle-panel-history')
        < index.index('data-lifecycle-panel-storage')
    )
    assert 'Only approved lifecycle domains are manageable.' in index
    assert 'Canonical queue, progress, results, and worker metadata.' in presentation


def test_data_lifecycle_uses_shared_kaori_loading_bar() -> None:
    policy = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')

    for source in (policy, history):
        assert 'components/loading_bar.html' in source
        assert 'notification-progress-indeterminate' not in source
    assert "loading_bar.render('data-lifecycle-policy-loading'" in policy
    assert "loading_bar.render('data-lifecycle-history-loading'" in history


def test_retention_policy_explains_schedule_failure_and_worker_semantics() -> None:
    policy = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    tasks = read('app/retention/tasks.py')
    config = read('app/config/default.py')

    assert 'Changing retention days only changes eligibility; it does not run a job immediately.' in policy
    assert 'Requires Policy enabled + Scheduled execution.' in policy
    assert 'Transient failures retry once; exhausted failures require manual retry.' in policy
    assert 'Queue {{ lifecycle.queue_name }} · {{ lifecycle.worker.label }}.' in policy
    assert "crontab(minute='*/15')" in config
    assert "name='app.retention.tasks.run_scheduled_retention'" in tasks
    assert 'acks_late=True' in tasks
    assert 'reject_on_worker_lost=True' in tasks
    assert '_is_retryable_retention_error' in tasks
    assert 'execution.retrying(' in tasks
    assert 'self.retry(exc=exc, countdown=retry_delay, max_retries=1)' in tasks
    assert 'RETENTION_RETRY_DELAY_SECONDS' in config


def test_archive_storage_is_operational_evidence_not_a_metric_stub() -> None:
    storage = read('app/templates/platform_operations/data_lifecycle/partials/_storage.html')

    for token in (
        'Storage Readiness',
        'Worker Readiness',
        'Last Verified',
        'Archive Format',
        'Archive Target Contract',
        'Execution Contract',
        'Archive-First Safety Boundary',
        'Freeze Boundary',
        'Write Archive',
        'Verify Evidence',
        'Cleanup Hot Data',
        'Storage Interpretation',
        'Production uses the dedicated maintenance worker service.',
    ):
        assert token in storage
    assert 'ARCHIVE_S3_SECRET_ACCESS_KEY' not in storage
    assert 'ARCHIVE_S3_ACCESS_KEY_ID' not in storage


def test_archive_history_rows_typography_uses_shared_pagination_geometry() -> None:
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')

    assert 'pagination_ui.footer_classes()' in history
    assert 'pagination_ui.summary_group_classes()' in history
    assert 'pagination_ui.rows_group_classes()' in history
    assert '<span class="text-xs font-semibold text-content-secondary">Rows</span>' in history
    assert 'aria-label="Rows Per Page"' in history


def test_dark_sidebar_active_parent_has_no_separate_left_edge_violet_accent() -> None:
    styles = read('frontend/styles.css')
    sidebar_doc = read('docs/design/components/SIDEBAR_NAVIGATION.md')

    assert 'box-shadow: inset 3px 0 0 var(--kaori-brand-primary)' not in styles
    assert 'box-shadow: 0 8px 20px rgba(5, 3, 9, 0.24)' in styles
    assert 'dark mode keeps the active Violet surface without a separate left-edge accent' in sidebar_doc
