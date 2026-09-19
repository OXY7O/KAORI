from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_archive_selection_uses_one_frozen_selection_timestamp_end_to_end() -> None:
    types = read('app/platform_operations/data_lifecycle/retention/types.py')
    service = read('app/platform_operations/data_lifecycle/retention/service.py')

    assert 'selected_at: datetime' in types
    assert "'selection_as_of': _isoformat(boundary.selected_at)" in service
    assert "'selected_at': _isoformat(boundary.selected_at)" in service

    for relative in (
        'app/platform_operations/data_lifecycle/retention/domains/operational_activity.py',
        'app/platform_operations/data_lifecycle/retention/domains/job_execution.py',
        'app/platform_operations/data_lifecycle/retention/domains/runtime_observation.py',
        'app/platform_operations/data_lifecycle/retention/domains/analytics_snapshot.py',
        'app/platform_operations/data_lifecycle/retention/domains/generated_report.py',
    ):
        assert 'selected_at=now' in read(relative)

    job_execution = read('app/platform_operations/data_lifecycle/retention/domains/job_execution.py')
    generated_report = read('app/platform_operations/data_lifecycle/retention/domains/generated_report.py')
    assert 'selection_now = boundary.selected_at' in job_execution
    assert job_execution.count('now=selection_now') >= 1
    assert generated_report.count('selection_now = boundary.selected_at') >= 3
    assert generated_report.count('now=selection_now') >= 3


def test_data_lifecycle_reads_do_not_create_policy_rows_and_all_runtime_domains_are_seeded() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    tasks = read('app/platform_operations/data_lifecycle/retention/tasks.py')
    policy_service = read('app/platform_operations/data_lifecycle/retention/policy_service.py')
    migration = read('migrations/versions/20260817_lifecycle_policy_seed.py')

    assert 'def get_policy(domain: str) -> DataLifecyclePolicy | None:' in policy_service
    assert 'get_or_create_policy' not in presentation
    assert 'get_or_create_policy' not in tasks
    assert 'stored_policy = get_policy(domain_name)' in tasks
    assert "revision = '20260817_lifecycle_policy_seed'" in migration
    assert "down_revision = '20260816_schedule_run_evidence'" in migration
    assert "'domain': 'runtime_observation'" in migration
    assert "'domain': 'analytics_snapshot'" in migration
    assert 'if exists is None:' in migration


def test_data_lifecycle_top_level_workspaces_are_server_owned_and_demand_loaded() -> None:
    index = read('app/templates/platform_operations/data_lifecycle/index.html')
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')

    assert 'framed_workspace_tabs.render_navigation(' in index
    assert "hx_target='#data-lifecycle-workspace-shell'" in index
    assert "lifecycle.active_tab == 'history'" in index
    assert "lifecycle.active_tab == 'storage'" in index
    assert 'x-show="activeTab' not in index
    assert "if active == 'policies':" in presentation
    assert "if active == 'history':" in presentation
    assert '_latest_verified_archive_for_profile(storage_profile, supported)' in presentation


def test_shared_archive_storage_uses_verified_evidence_from_current_storage_profile() -> None:
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    storage_presentation = read('app/platform_operations/data_lifecycle/retention/storage_presentation.py')

    assert 'def _latest_verified_archive_for_profile(' in presentation
    assert 'ArchiveArtifact.domain.in_(domain_names)' in presentation
    assert 'ArchiveArtifact.storage_backend == profile.backend' in presentation
    assert '.yield_per(100)' in presentation
    assert 'storage_ui.artifact_matches_storage_profile(item, profile)' in presentation
    assert 'def artifact_matches_storage_profile(' in storage_presentation


def test_manual_execution_is_fail_closed_for_invalid_mode_missing_policy_or_paused_policy() -> None:
    service = read('app/platform_operations/data_lifecycle/service.py')
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')

    assert "normalized_mode not in {'archive_only', 'archive_and_cleanup'}" in service
    assert 'stored_policy = get_policy(domain_name)' in service
    assert 'if stored_policy is None or not policy.enabled:' in service
    assert "reason = 'policy_missing' if stored_policy is None else 'policy_disabled'" in service
    assert "'enabled': bool(stored.enabled) if stored is not None else False" in presentation
    assert 'operation=normalized_mode' in service
    assert '{% set execution_blocked = (not selected.enabled) or lifecycle.active_lifecycle_jobs %}' in workspace
    assert workspace.count('{% if execution_blocked %}disabled{% endif %}') >= 2
    assert 'Policy paused.' in workspace


def test_active_policy_polling_is_bounded_and_pauses_for_hidden_browser_tabs() -> None:
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')

    assert 'hx-trigger="every 10s"' in workspace
    assert 'if (document.hidden) event.preventDefault()' in workspace
    assert 'every 4s' not in workspace
    assert 'Boundary evaluated at {{ lifecycle.preview.selected_at|user_datetime }}' in workspace


def test_archive_history_preserves_registry_context_after_verification() -> None:
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')

    for name in (
        'archive_domain',
        'archive_status',
        'archive_trigger',
        'archive_mode',
        'archive_storage',
        'archive_search',
        'archive_page',
        'archive_per_page',
    ):
        assert f'name="{name}"' in history
    assert 'value="{{ pager.page }}"' in history
    assert 'value="{{ pager.per_page }}"' in history


def test_archive_purge_is_bounded_retryable_and_never_advertises_partial_objects_as_downloadable() -> None:
    model = read('app/models/archive.py')
    service = read('app/platform_operations/data_lifecycle/retention/service.py')
    tasks = read('app/platform_operations/data_lifecycle/retention/tasks.py')
    storage = read('app/templates/platform_operations/data_lifecycle/partials/_storage.html')
    history = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')
    config = read('app/config/default.py')

    assert "ARCHIVE_STATUS_PURGE_FAILED = 'purge_failed'" in model
    assert (
        'ARCHIVE_STATUS_PURGE_FAILED' not in model.split('def is_downloadable', 1)[1].split('def is_verifiable', 1)[0]
    )
    assert "current_app.config.get('ARCHIVE_PURGE_BATCH_SIZE', 250)" in service
    assert '.limit(batch_size)' in service
    assert '.all()' in service
    assert 'failed_artifact.status = ARCHIVE_STATUS_PURGE_FAILED' in service
    assert "'failed_count': len(candidates) - purged_count" in service
    assert 'partial=purge_partial' in tasks
    assert "ARCHIVE_PURGE_BATCH_SIZE = _bounded_env_int('ARCHIVE_PURGE_BATCH_SIZE', 250, 25, 2500)" in config
    assert 'Archive Purge Batch' in storage
    assert 'Purge Failed' in storage
    assert "archive.status in ['failed', 'purge_failed']" in history


def test_persisted_policy_scheduler_is_not_disabled_by_legacy_domain_environment_booleans() -> None:
    config = read('app/config/default.py')
    presentation = read('app/platform_operations/data_lifecycle/retention/presentation.py')
    workspace = read('app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html')
    storage = read('app/templates/platform_operations/data_lifecycle/partials/_storage.html')

    assert "if _env_bool('DATA_LIFECYCLE_SCHEDULER_ENABLED', True):" in config
    assert "'data-lifecycle-dispatcher'" in config
    assert "DATA_LIFECYCLE_SCHEDULER_ENABLED = _env_bool('DATA_LIFECYCLE_SCHEDULER_ENABLED', True)" in config
    assert "scheduler_enabled = bool(current_app.config.get('DATA_LIFECYCLE_SCHEDULER_ENABLED', True))" in presentation
    assert 'schedule_enabled and scheduler_enabled' in presentation
    assert 'global Data Lifecycle dispatcher is disabled' in workspace
    assert 'Disabled globally' in storage
