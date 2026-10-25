from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_terminal_status_refresh_does_not_replace_configuration_forms() -> None:
    workspace = _read('app/templates/platform_operations/jobs/configuration/_job_workspace.html')
    poller = _read('app/templates/platform_operations/jobs/configuration/_live_poller.html')
    response = _read('app/templates/platform_operations/jobs/configuration/_live_status_response.html')
    routes = _read('app/platform_operations/jobs/routes.py')

    assert 'hx-trigger="every 2s"' not in workspace
    assert 'job-configuration-live-poller' in poller
    assert '_execution_activity.html' in response
    assert '_selected_status.html' in response
    assert "@bp.get('/configuration/<path:job_key>/status')" in routes
    assert "render_template('platform_operations/jobs/configuration/_live_status_response.html'" in routes


def test_active_queries_ignore_completed_executions() -> None:
    for relative in (
        'app/kubernetes/inventory/job_adapter.py',
        'app/kubernetes/governance/tls_certificates/job_adapter.py',
        'app/kubernetes/analytics/job_adapter.py',
    ):
        content = _read(relative)
        assert 'JobExecution.completed_at.is_(None)' in content


def test_every_registered_job_uses_shared_execution_and_recent_activity_workspace() -> None:
    for relative in (
        'app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/tls_certificate_sync.html',
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html',
    ):
        content = _read(relative)
        assert 'platform_operations/jobs/configuration/_job_overview.html' in content
        assert 'platform_operations/jobs/configuration/_execution_activity.html' in content
        assert 'lg:grid-cols-2 lg:items-start' not in content
        assert 'xl:sticky' not in content

    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    assert 'Execution &amp; Recent Activity' in activity
    assert 'Recent Executions' in activity
    assert 'definition.recent_execution_summary' in activity
    assert 'Execution Safety:' in activity


def test_precomputed_ranges_are_compact_and_not_forced_into_seven_columns() -> None:
    analytics = _read('app/templates/platform_operations/jobs/configuration/definitions/analytics_refresh.html')
    forecast = _read('app/templates/platform_operations/jobs/configuration/definitions/forecast_refresh.html')

    assert 'Precomputed Time Ranges' in analytics
    assert 'sm:grid-cols-2 lg:grid-cols-4' in analytics
    assert 'xl:grid-cols-7' not in analytics
    assert 'Precomputed History Windows' in forecast
    assert 'sm:grid-cols-3' in forecast


def test_job_definitions_provide_job_specific_execution_history_descriptions() -> None:
    content = _read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    assert content.count('execution_summary:') >= 7
    assert content.count('recent_execution_summary:') >= 7


def test_registered_job_configuration_templates_use_canonical_platform_operations_namespace() -> None:
    catalog = _read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    template_names = [
        line.split(':', 1)[1].strip()
        for line in catalog.splitlines()
        if line.strip().startswith('configuration_template:')
    ]
    assert template_names
    for template_name in template_names:
        assert template_name.startswith('platform_operations/jobs/configuration/definitions/')
        assert (ROOT / 'app/templates' / template_name).is_file(), template_name


def test_job_configuration_one_line_helpers_preserve_source_evidence() -> None:
    overview = _read('app/templates/platform_operations/jobs/configuration/_job_overview.html')
    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    inventory = _read('app/templates/platform_operations/jobs/configuration/definitions/inventory_sync.html')
    tenant = _read('app/templates/platform_operations/jobs/configuration/definitions/tenant_sync.html')
    storage = _read(
        'app/templates/platform_operations/jobs/configuration/definitions/object_storage_inventory_sync.html'
    )

    assert 'sm:grid-cols-2 2xl:grid-cols-4' in overview
    assert "label == 'Next Automatic Run'" in overview
    assert 'whitespace-nowrap text-xs tabular-nums' in overview
    assert 'title="{{ value }}"' in overview
    assert 'title="{{ helper }}"' in overview
    assert 'xl:truncate' in overview
    assert 'lg:truncate' in activity
    assert 'same execution and audit trail' in activity
    assert 'whitespace-nowrap' in activity
    for source in (inventory, tenant, storage):
        assert 'schedule_policy.controls(' in source
    shared = _read('app/templates/platform_operations/jobs/configuration/_schedule_policy.html')
    assert 'block truncate text-xs leading-5' in shared
    assert 'title="{{ helper }}"' in shared
    assert 'Guarded Recovery Boundary' in storage
    assert "variant='guide'" in storage
    assert 'Two complete reads required; mismatches preserve committed records.' in storage
    assert 'mismatch or changed evidence fails closed' in storage.lower()
    assert 'name="confirmation_phrase"' in storage
    assert 'name="confirm_empty_system_id"' in storage


def test_vault_one_line_operator_guidance_retains_canonical_safety_evidence() -> None:
    overview = _read('app/templates/platform_operations/jobs/configuration/_job_overview.html')
    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    folder = 'app/templates/platform_operations/jobs/configuration/definitions/'
    templates = {
        'kv': _read(folder + 'secrets_pki_inventory_sync.html'),
        'alert': _read(folder + 'vault_alert_observation.html'),
        'issuer': _read(folder + 'secrets_pki_pki_sync.html'),
        'stored': _read(folder + 'secrets_pki_stored_cert_sync.html'),
    }

    assert 'overview_notice_short|default(overview_notice)' in overview
    assert 'title="{{ overview_notice }}"' in overview
    assert 'selected_description|default(definition.description)' in overview
    assert 'components/info_tip.html' in overview
    assert "variant='guide'" in overview
    assert 'execution_safety_short|default(definition.safety_summary)' in activity
    assert 'title="{{ definition.safety_summary }}"' in activity
    assert 'info_tip.render(' not in activity
    assert 'title="{{ active_job.progress_process }}"' in activity
    assert 'title="{{ active_job.progress_detail }}"' in activity
    assert 'xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.95fr)]' in activity
    assert 'items=[definition.safety_summary]' in overview
    assert 'jobs-selected-safety-' in overview
    assert 'items=[definition.safety_summary]' in overview
    assert "if overview_notice_short|default('') or execution_safety_short|default('')" not in overview
    for key, source in templates.items():
        assert 'overview_notice_short' in source, key
        assert 'policy_form.hidden_tag()' in source or key == 'alert'
    for key in ('kv', 'issuer', 'stored'):
        source = templates[key]
        assert 'schedule_policy.header(' in source
        assert 'schedule_policy.controls(' in source
        assert 'schedule_policy.timeline(policy)' in source
        assert 'schedule_policy.footer(' in source
        assert 'Saved policy takes effect on the next scheduler cycle.' in source
        assert 'policy_form.hidden_tag()' in source
    assert 'worker-only HMAC' in templates['alert']
    assert 'no_store/imported certificates are not enumerable' in templates['stored']
    assert 'Over 64 stored certificates blocks collection' in templates['stored']


def test_materialization_one_line_copy_retains_policy_and_safety() -> None:
    source = _read('app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html')
    definition = _read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    assert 'lg:grid-cols-12 lg:items-stretch' in source
    shared = _read('app/templates/platform_operations/jobs/configuration/_schedule_policy.html')
    assert 'min-h-[7rem]' in shared
    assert 'min-h-[9rem]' in source
    assert 'Run snapshot refreshes from the saved policy.' in source
    assert 'Keep the last successful snapshot available.' in source
    assert 'object_storage.analytics.materialize' in source
    assert 'execution_safety_short' in source
    assert 'The last usable snapshot remains available inside the stale-grace window.' in definition
    assert 'schedule_policy.toggle(' in source
    assert 'schedule_policy.interval(' in source
    assert 'schedule_policy.header(' in source
    assert 'schedule_policy.footer(' in source
    assert 'policy_form.stale_grace_minutes(' in source
    assert 'policy_form.freshness_minutes(' in source


def test_job_policy_cards_have_guidance_without_mutating_policy_controls() -> None:
    folder = 'app/templates/platform_operations/jobs/configuration/definitions/'
    vault_templates = (
        'secrets_pki_inventory_sync.html',
        'secrets_pki_pki_sync.html',
        'secrets_pki_stored_cert_sync.html',
    )
    registry_templates = (
        'artifact_registry_security_sync.html',
        'artifact_registry_governance_sync.html',
    )
    for name in vault_templates:
        source = _read(folder + name)
        assert 'schedule_policy.header(' in source
        assert 'schedule_policy.controls(' in source
        assert 'schedule_policy.timeline(policy)' in source
        assert 'schedule_policy.footer(' in source
        assert 'policy_form.hidden_tag()' in source
        assert 'Saved policy takes effect on the next scheduler cycle.' in source
    for name in registry_templates:
        source = _read(folder + name)
        assert 'schedule_policy.controls(' in source
        assert 'schedule_policy.footer(' in source
        assert 'policy_form.hidden_tag()' in source

    registry_analytics = _read(folder + 'artifact_registry_analytics_refresh.html')
    assert 'execution_safety_short' in registry_analytics
    assert 'Analytics reads committed Registry and qualified Metrics Source' in registry_analytics


def test_selected_job_guide_is_title_level_and_execution_progress_is_one_line() -> None:
    overview = _read('app/templates/platform_operations/jobs/configuration/_job_overview.html')
    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    assert 'jobs-selected-safety-' in overview
    assert "variant='guide'" in overview
    assert 'items=[definition.safety_summary]' in overview
    assert overview.index('jobs-selected-safety-') < overview.index('selected_description|default')
    assert 'jobs-overview-safety-' not in overview
    assert 'info_tip.render(' not in activity
    assert 'execution_safety_short|default(definition.safety_summary)' in activity
    assert 'title="{{ active_job.progress_process }}"' in activity
    assert 'title="{{ active_job.progress_detail }}"' in activity
    assert 'progress_bar.job_progress(active_job' in activity
    assert "url_for('jobs.run_now', job_key=definition.key)" in activity


def test_shared_kubernetes_schedule_ui_is_used_by_normal_scheduled_jobs() -> None:
    base = 'app/templates/platform_operations/jobs/configuration/definitions/'
    templates = (
        'inventory_sync.html',
        'tenant_sync.html',
        'object_storage_inventory_sync.html',
        'artifact_registry_inventory_sync.html',
        'artifact_registry_security_sync.html',
        'artifact_registry_governance_sync.html',
        'artifact_registry_runtime_correlation.html',
        'report_schedule.html',
        'tls_certificate_sync.html',
        'source_control_repository_sync.html',
    )
    shared = _read('app/templates/platform_operations/jobs/configuration/_schedule_policy.html')
    for block in ('header', 'controls', 'timeline', 'footer'):
        assert '{% macro ' + block + '(' in shared
    for filename in templates:
        source = _read(base + filename)
        for block in ('header', 'controls', 'footer'):
            assert 'schedule_policy.' + block + '(' in source, filename
        assert 'policy_form.hidden_tag()' in source
        assert '_job_overview.html' in source
        assert '_execution_activity.html' in source


def test_all_specialized_jobs_reuse_policy_primitives_without_losing_domain_fields() -> None:
    base = 'app/templates/platform_operations/jobs/configuration/definitions/'
    shared = _read('app/templates/platform_operations/jobs/configuration/_schedule_policy.html')
    assert '{% macro toggle(' in shared
    assert '{% macro interval(' in shared
    assert '{% macro manual_header(' in shared
    assert 'policy_form.enabled(' in shared
    assert 'policy_form.interval_minutes(' in shared
    for filename in (
        'secrets_pki_inventory_sync.html',
        'secrets_pki_pki_sync.html',
        'secrets_pki_stored_cert_sync.html',
    ):
        source = _read(base + filename)
        assert 'schedule_policy.controls(' in source
        assert 'policy_form.hidden_tag()' in source
    materialization = _read(base + '_materialization_job.html')
    assert 'schedule_policy.toggle(' in materialization
    assert 'schedule_policy.interval(' in materialization
    assert 'policy_form.freshness_minutes(' in materialization
    assert 'policy_form.stale_grace_minutes(' in materialization
    assert '{% block materialization_options %}' in materialization
    manual_only = _read(base + 'vault_alert_observation.html')
    assert 'schedule_policy.manual_header(' in manual_only
    assert 'policy_form.enabled(' not in manual_only


def test_guarded_recovery_guide_is_adjacent_to_title_and_mutation_stays_guarded() -> None:
    base = 'app/templates/platform_operations/jobs/configuration/definitions/'
    for name, identity in (
        ('object_storage_inventory_sync.html', 'confirm_empty_system_id'),
        ('artifact_registry_inventory_sync.html', 'confirm_empty_instance_id'),
    ):
        source = _read(base + name)
        guide = source.index('Guarded Recovery Boundary')
        title = source.index('Confirm an Empty')
        helper = source.index('Verify intentional')
        assert title < guide < helper, name
        assert 'mt-1 flex min-w-0 flex-wrap items-center gap-2' in source
        assert 'border-b border-kaori-primary/15 bg-kaori-soft' in source
        assert 'bg-status-warning-soft text-status-warning-text shadow-sm' in source
        assert 'mt-1 text-xs leading-5 text-content-muted' in source
        assert source.count('Guarded Recovery Boundary') == 1
        assert 'manual_form.hidden_tag()' in source
        assert 'name="empty_reconciliation" value="confirm"' in source
        assert 'name="confirmation_phrase"' in source
        assert f'name="{identity}"' in source
        assert 'selected_job.active_job or selected_job.execution_disabled' in source
        assert 'Two complete reads required; mismatches preserve committed records.' in source


def test_execution_scope_and_source_control_evidence_have_compact_accurate_previews() -> None:
    activity = _read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')
    source = _read(
        'app/templates/platform_operations/jobs/configuration/definitions/source_control_repository_sync.html'
    )
    assert 'min-w-0 truncate whitespace-nowrap' in activity
    assert 'title="{{ selected_job.execution_scope_label }}"' in activity
    assert '{{ selected_job.execution_scope_label }}' in activity
    assert 'overview_notice_short' in source
    assert 'execution_safety_short' in source
    assert 'Scheduling is disabled by default.' in source
    assert 'Incomplete scans preserve committed evidence' in source
    assert 'policy_form.hidden_tag()' in source


def test_report_channels_use_bounded_accessible_collection_without_mutating_dispatch() -> None:
    source = _read('app/templates/platform_operations/jobs/configuration/definitions/report_schedule.html')
    assert 'job-delivery-channels-title' in source
    assert 'selected_job.delivery_channels|length' in source
    assert 'max-h-64' in source
    assert 'overflow-y-auto' in source
    assert 'divide-y divide-outline-subtle' in source
    assert 'flex min-w-0 items-center justify-between gap-3 px-4 py-2.5' in source
    assert 'title="{{ channel.label }}"' in source
    assert 'title="{{ channel.description }}"' in source
    assert "table_label.status_label(channel.status, channel.tone, none, 'detail')" in source
    assert 'No delivery channels configured.' in source
    assert 'tabindex="0"' in source
    assert 'policy_form.hidden_tag()' in source
    assert 'schedule_policy.footer(' in source


def test_jobs_catalog_footer_follows_data_lifecycle_boundary_guidance_pattern() -> None:
    jobs = _read('app/templates/platform_operations/jobs/configuration/_workspace.html')
    lifecycle = _read('app/templates/platform_operations/data_lifecycle/index.html')
    for component in ('Execution Boundary', "url_for('jobs.executions')", "variant='guide'"):
        assert component in jobs
        assert component in lifecycle
    assert "current_user.has_permission('jobs.view')" in jobs
    assert 'x-text="visibleJobCount"' in jobs
    assert 'jobs-configuration-catalog-guide' in jobs
    assert 'overflow-x-auto whitespace-nowrap' in jobs
    assert 'aria-label="Job configuration execution boundary and navigation"' in jobs
    assert 'ml-auto inline-flex shrink-0' in jobs
    assert 'border-l border-outline-subtle pl-2' in jobs
