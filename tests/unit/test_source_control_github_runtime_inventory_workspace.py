"""GitHub Runtime & Inventory UAT parity contracts (#3306)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITHUB = ROOT / 'app/templates/integrations/source_control/github'
ROUTES = ROOT / 'app/integrations/source_control/source_control/providers/github/application/uat_routes.py'
RUNTIME_PRESENTATION = (
    ROOT / 'app/integrations/source_control/source_control/providers/github/application/runtime_presentation.py'
)


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_runtime_reuses_standard_decision_and_canonical_refresh():
    detail = _read(GITHUB / 'uat_detail.html')
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    jobs = _read(GITHUB / 'partials/_runtime_jobs.html')
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')
    routes = _read(ROUTES)

    assert 'partials/_detail_runtime.html' in detail
    for token in (
        'integrations/components/_runtime_decision.html',
        'components/connection_validation_header.html',
        'integrations/components/_validation_poller.html',
        'integrations/components/_provider_job_status.html',
        'runtime_decision.render(',
        'data-kaori-provider-runtime-kubernetes-pattern',
        'runtime_observed',
        'Run Runtime Refresh',
        'action_form.hidden_tag()',
        'hx-post=',
        'partials/_runtime_jobs.html',
        'partials/_runtime_deliveries.html',
    ):
        assert token in runtime
    assert "operation='runtime_refresh'" in routes
    assert 'def runtime_refresh(installation_id: int)' in routes
    assert 'def runtime_refresh_status(installation_id: int, task_id: str)' in routes
    assert "snapshot.get('operation') != 'runtime_refresh'" in routes
    assert 'validate_snapshot_access(' in routes
    assert 'integration_instance_id=installation.integration_instance_id' in routes
    assert 'FlaskForm().validate_on_submit()' in routes
    assert 'provider.refresh(' not in routes
    assert 'requests.get(' not in routes
    assert 'jobs' in jobs and 'deliveries' in deliveries
    assert 'delivery.dispatched_job_execution_id' in deliveries
    assert 'delivery.payload_sha256' not in deliveries


def test_history_registries_are_scoped_server_filtered_paginated():
    runtime_source = _read(RUNTIME_PRESENTATION)
    jobs = _read(GITHUB / 'partials/_runtime_jobs.html')
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')

    assert "JobExecution.integration_type == 'source_control'" in runtime_source
    assert 'JobExecution.integration_instance_id == installation.integration_instance_id' in runtime_source
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in runtime_source
    assert "operation='runtime_refresh'" in runtime_source
    assert 'runtime_refresh_job' in runtime_source
    assert 'paginate_query(' in runtime_source
    for panel, field in ((jobs, 'job_per_page'), (deliveries, 'delivery_per_page')):
        assert 'data-kaori-server-filtered-registry' in panel
        assert 'components/table.html' in panel
        assert 'components/pagination.html' in panel
        # Loading is owned by the canonical table header rather than a page-local import.
        assert 'table_ui.inventory_block_header(' in panel
        assert 'hx-swap="outerHTML"' in panel
        assert 'data-kaori-auto-submit' in panel
        assert field in panel
        assert 'selected' in panel


def test_inventory_follows_kubernetes_decision_and_committed_scope():
    detail = _read(GITHUB / 'uat_detail.html')
    inventory = _read(GITHUB / 'partials/_detail_inventory.html')
    registry = _read(GITHUB / '_inventory_table.html')
    routes = _read(ROUTES)
    projection = _read(ROOT / 'app/integrations/source_control/repository_inventory.py')

    assert 'partials/_detail_inventory.html' in detail
    assert 'data-kaori-inventory-lifecycle-decision' in inventory
    assert 'data-kaori-github-inventory-snapshot' in inventory
    assert 'data-kaori-inventory-lifecycle-boundary' in inventory
    assert 'Provider Authority' in inventory
    assert 'Historical Evidence Preserved' in inventory
    assert "readiness == 'ready'" in inventory
    assert "url_for('github_source_uat.synchronize', installation_id=installation.id)" in inventory
    assert 'action_form.hidden_tag()' in inventory
    assert 'inventory.total is not none' in inventory
    assert 'inventory.total is none' in registry
    assert 'inventory.total == 0' in registry
    assert 'matching_total' in registry
    assert "inventory.total if committed else 'Unknown'" in inventory
    assert 'exact_default_branch_sha' in registry
    assert 'revision_observed_at' in registry
    assert 'components/table.html' in registry
    assert 'components/pagination.html' in registry
    assert '[5, 10, 25, 50]' in registry
    assert 'hx-trigger="every 15s"' in registry
    assert 'read_installation_inventory_for_current_session(' in routes
    assert 'authorized_installation_id=installation.id' in routes
    assert 'committed_generation == 0' in projection
    assert 'total=None' in projection
    assert 'github.com/settings' not in inventory


def test_copy_is_short_and_provider_evidence_not_overclaimed():
    validation = _read(GITHUB / 'partials/_detail_validation.html')
    assert 'Validate GitHub App identity and read permissions before repository sync.' in validation
    assert (
        'GitHub owns permissions; KAORI commits inventory and exact source revisions after synchronization.'
        in validation
    )
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    assert 'not repository synchronization or provider-side runtime history' in runtime
    assert 'registration' not in runtime.lower()


def test_github_connection_save_uses_operational_toast_not_persistent_banner():
    detail = _read(GITHUB / 'uat_detail.html')
    routes = _read(ROUTES)
    app = _read(ROOT / 'app/templates/layouts/app.html')

    assert "feedback not in ['configuration_updated', 'configuration_revalidation_required']" in detail
    assert '"configuration_updated":' in detail
    assert 'feedback in feedback_map and feedback not in' in detail
    assert "event_type='source_control_connection_updated'" in routes
    assert 'queue_feedback=True' in routes
    assert 'components/operational_toast.html' in app


def test_github_header_help_reuses_accessible_kaori_info_tip():
    detail = _read(GITHUB / 'uat_detail.html')
    validation = _read(GITHUB / 'partials/_detail_validation.html')
    inventory = _read(GITHUB / 'partials/_detail_inventory.html')
    header = _read(ROOT / 'app/templates/components/connection_validation_header.html')

    assert 'title_extra=connection_title_tip' in detail
    assert 'github-connection-contract-guide' in detail
    assert 'github-full-validation-guide' in validation
    assert 'github-inventory-lifecycle-guide' in inventory
    assert 'components/info_tip.html' in validation
    assert 'components/info_tip.html' in inventory
    assert 'title_extra=None' in header
    assert 'if title_extra' in header
    for source in (detail, validation, inventory):
        assert "variant='guide'" in source
    # KAORI title-level guidance uses the visible Guide trigger, never a bare question-mark icon.


def test_github_runtime_history_is_one_accessible_two_tab_registry():
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    jobs = _read(GITHUB / 'partials/_runtime_jobs.html')
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')
    routes = _read(ROUTES)
    runtime_source = _read(RUNTIME_PRESENTATION)
    framed_tabs = _read(ROOT / 'app/templates/components/framed_workspace_tabs.html')

    assert 'framed_tabs.render_navigation(' in runtime
    assert 'data-kaori-github-runtime-registry-tabs' in runtime
    assert 'id="github-runtime-evidence-registry"' in runtime
    assert "runtime_view == 'deliveries'" in runtime
    assert 'runtime_table_embedded = true' in runtime
    assert runtime.count('partials/_runtime_jobs.html') == 1
    assert runtime.count('partials/_runtime_deliveries.html') == 1
    assert 'render_navigation(' in framed_tabs
    assert 'data-kaori-tab-variant="framed-workspace-v2-server"' in framed_tabs
    assert "hx_target='#github-runtime-evidence-registry'" in runtime
    assert "hx_select='#github-runtime-evidence-registry'" in runtime
    assert "hx_push_url='true'" in runtime
    assert "('jobs', 'Recent Jobs', 'history'" in runtime
    assert "('deliveries', 'Signed Webhook Deliveries', 'webhook'" in runtime
    for page, kind in ((jobs, 'jobs'), (deliveries, 'deliveries')):
        assert f'data-kaori-runtime-registry-view="{kind}"' in page
        assert f"runtime_view='{kind}'" in page
        assert 'runtime_table_embedded|default(false)' in page
        assert 'components/pagination.html' in page
        assert 'table_ui.inventory_block_header(' in page
        assert 'data-kaori-auto-submit' in page
        assert 'registry_ui.clear_filters_action(' in page
    assert routes.count('runtime_table_embedded=True') == 2
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in runtime_source


def test_github_committed_repository_registry_is_full_width_sibling():
    decision = _read(GITHUB / 'partials/_detail_inventory.html')
    registry = _read(GITHUB / '_inventory_table.html')
    table = _read(ROOT / 'app/templates/components/table.html')

    assert 'github-inventory-lifecycle-guide' in decision
    assert decision.index('</section>\n{% include "integrations/source_control/github/_inventory_table.html" %}') > 0
    assert '<section id="source-control-inventory"' in registry
    assert 'table_ui.block_classes(allow_overflow=true)' in registry
    assert "table_ui.table_classes('min-w-[800px] table-fixed xl:min-w-0')" in registry
    assert '<caption class="sr-only">' in registry
    assert 'scope="col"' in registry
    assert 'macro block_classes(' in table
    assert 'inventory.total is none' in registry
    assert 'inventory.total == 0' in registry
    assert 'exact_default_branch_sha' in registry


def test_runtime_health_uses_approved_labeled_guide_header():
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    header = _read(ROOT / 'app/templates/components/connection_validation_header.html')
    assert 'components/info_tip.html' in runtime
    assert 'title_extra=info_tip.render(' in runtime
    assert "'github-runtime-health-guide'" in runtime
    assert "placement='right', variant='guide'" in runtime
    assert 'title_extra=None' in header
    assert '{% if title_extra %}{{ title_extra }}{% endif %}' in header
    assert 'Signed webhook deliveries are transport evidence' in runtime


def test_runtime_history_uses_full_kaori_table_components():
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    shared_table = _read(ROOT / 'app/templates/components/table.html')
    shared_registry = _read(ROOT / 'app/templates/components/table_registry.html')
    assert 'framed_tabs.render_navigation(' in runtime
    assert 'macro inventory_block_header(' in shared_table
    assert 'macro clear_filters_action(' in shared_registry
    for filename, view in (('_runtime_jobs.html', 'jobs'), ('_runtime_deliveries.html', 'deliveries')):
        page = _read(GITHUB / 'partials' / filename)
        assert f'data-kaori-full-table-registry="{view}"' in page
        for token in (
            'table_ui.inventory_block_header(',
            'title_extra=header_guide',
            "variant='guide'",
            'registry_ui.clear_filters_action(',
            'table_ui.inventory_filter_bar_classes()',
            'table_ui.filter_layout_classes()',
            'table_ui.filter_select_classes()',
            'data-kaori-canonical-registry-filter',
            'hx-sync="closest section:replace"',
            "table_ui.table_classes('min-w-[800px] table-fixed xl:min-w-0')",
            'table_ui.title_cell(',
            '<caption class="sr-only">',
            'scope="col"',
            'components/states/_empty_state.html',
            'data-kaori-canonical-registry-footer',
            'data-kaori-page-size-control',
            'data-kaori-auto-submit',
            'pagination_ui.numeric_pages(',
            'integration_status(',
        ):
            assert token in page, (filename, token)
        assert f"runtime_view='{view}'" in page
        assert 'payload_sha256' not in page


def test_runtime_filter_controls_and_kaori_tab_counters():
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    jobs = _read(GITHUB / 'partials/_runtime_jobs.html')
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')
    routes = _read(ROUTES)
    runtime_source = _read(RUNTIME_PRESENTATION)

    # The full table owns result counts; tab labels must remain text-only.
    tabs = runtime.split('{% set runtime_tabs = [', 1)[1].split('] %}', 1)[0]
    assert "'Recent Jobs'" in tabs
    assert "'Signed Webhook Deliveries'" in tabs
    assert 'total_items' not in tabs
    for page, fields, view in (
        (jobs, ('job_search', 'job_queue', 'job_status'), 'jobs'),
        (deliveries, ('delivery_search', 'delivery_event', 'delivery_state'), 'deliveries'),
    ):
        assert page.count('type="search"') == 1
        for field in fields:
            assert f'name="{field}"' in page
            assert f"'{field}': {field}" in page
            assert f'{field}={field}' in page
            assert f'<input type="hidden" name="{field}"' in page or field == fields[0]
        assert 'hx-trigger="change, input changed delay:400ms, submit"' in page
        assert 'registry_ui.clear_filters_action(' in page
        assert f"runtime_view='{view}'" in page

    assert "JobExecution.integration_type == 'source_control'" in runtime_source
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in runtime_source
    assert 'JobExecution.queue_name == job_queue' in runtime_source
    assert 'SourceWebhookDelivery.event_type == delivery_event' in runtime_source
    assert 'JobExecution.operation.ilike(' in runtime_source
    assert 'SourceWebhookDelivery.action.ilike(' in runtime_source
    assert "request.args.get('job_search', '').strip()[:80]" in runtime_source
    assert "request.args.get('delivery_search', '').strip()[:80]" in runtime_source
    assert '.limit(50)' in runtime_source
    assert "return '%' + value.replace(" in runtime_source
    assert 'requests.get(' not in routes


def test_runtime_search_escapes_sql_like_wildcards():
    from app.integrations.source_control.source_control.providers.github.application.uat_routes import (
        _runtime_search_pattern,
    )

    assert _runtime_search_pattern('runtime_refresh') == r'%runtime\_refresh%'
    assert _runtime_search_pattern('100%') == r'%100\%%'
    assert _runtime_search_pattern('job') == '%job%'


def test_runtime_history_filters_are_automatic_and_rows_are_readable():
    jobs = _read(GITHUB / 'partials/_runtime_jobs.html')
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')

    for panel in (jobs, deliveries):
        assert 'hx-trigger="change, input changed delay:400ms, submit"' in panel
        assert 'data-kaori-canonical-registry-filter=' in panel
        assert 'registry_ui.clear_filters_action(' in panel
        assert 'Apply Filters' not in panel
        assert '<noscript>' in panel
        assert '<button type="submit"' in panel
        assert 'Filter Results' in panel

    # Keep server-authoritative JobExecution fields and show a compact date/time pair.
    assert 'table_ui.title_cell(job.operation' in jobs
    assert "'Job #' ~ job.id" in jobs
    assert 'job.created_at.isoformat()' in jobs
    assert 'job.created_at.strftime("%d %b %Y")' in jobs
    assert 'job.created_at.strftime("%H:%M:%S")' in jobs
    assert 'tabular-nums' in jobs
    assert "job.queue_name or 'Not assigned'" in jobs
    assert "integration_status(job.status, display='indicator')" in jobs


def test_committed_repository_registry_uses_kaori_full_table_and_spacing():
    detail = _read(GITHUB / 'uat_detail.html')
    registry = _read(GITHUB / '_inventory_table.html')
    jobs = _read(GITHUB / 'partials/_runtime_jobs.html')

    assert 'id="github-panel-inventory"' in detail
    assert (
        'class="space-y-4"'
        in detail.split('id="github-panel-inventory"', 1)[1].split(
            '{% include "integrations/source_control/github/partials/_detail_inventory.html" %}', 1
        )[0]
    )
    for token in (
        'table_ui.inventory_block_header(',
        'title_extra=header_guide',
        'data-kaori-full-table-registry="repository-inventory"',
        'table_ui.inventory_filter_bar_classes()',
        'table_ui.filter_layout_classes()',
        'data-kaori-canonical-registry-filter="source-control-inventory"',
        'hx-trigger="change, input changed delay:400ms, submit"',
        'registry_ui.clear_filters_action(',
        'table_ui.title_cell(',
        'pagination_ui.numeric_pages(',
        'data-kaori-canonical-registry-footer="source-control-inventory"',
        'components/states/_empty_state.html',
    ):
        assert token in registry
    assert 'Apply Filters' not in registry
    assert '<noscript>' in registry
    assert 'inventory.total is none' in registry
    assert 'inventory.total == 0' in registry
    assert 'matching_total == 0' in registry
    assert 'row.exact_default_branch_sha' in registry
    assert 'observed_at.isoformat()' in registry
    assert 'job.created_at.strftime("%d %b %Y")' in jobs


def test_committed_repository_filters_preserve_installation_authority():
    routes = _read(ROUTES)
    projection = _read(ROOT / 'app/integrations/source_control/repository_inventory.py')
    registry = _read(GITHUB / '_inventory_table.html')

    assert "request.args.get('inventory_search', '').strip()[:80]" in routes
    assert "inventory_visibility not in {'public', 'private', 'internal', 'unknown'}" in routes
    assert "inventory_archived not in {'active', 'archived', 'unknown'}" in routes
    assert 'authorized_installation_id=installation.id' in routes
    assert 'matching_total: int | None = None' in projection
    assert 'SourceRepository.full_name.icontains(search, autoescape=True)' in projection
    assert 'SourceRepositoryGrant.installation_id == authorized_installation_id' in projection
    assert 'SourceRepositoryGrant.valid_until.is_(None)' in projection
    assert 'matching_total = total' in projection
    assert 'effective_page = min(page,' in projection
    for field in ('inventory_search', 'inventory_visibility', 'inventory_archived'):
        assert f'name="{field}"' in registry
        assert f"'{field}': {field}" in registry
        assert f'{field}={field}' in registry


def test_github_inventory_uses_lifecycle_deletion_and_sync_toast():
    detail = _read(GITHUB / 'uat_detail.html')
    inventory = _read(GITHUB / 'partials/_detail_inventory.html')
    routes = _read(ROUTES)
    repository = _read(ROOT / 'app/integrations/source_control/source_control/providers/github/application/repository.py')
    modal = _read(ROOT / 'app/templates/integrations/components/_asset_owner_delete_modal.html')

    assert '"sync_queued":' not in detail
    assert '"sync_blocked":' not in detail
    assert 'record_operational_activity(' in routes
    assert "'feedback_delivery': 'toast'" in routes
    assert 'Repository Sync Queued' in routes
    assert 'Repository Sync Blocked' in routes
    assert 'return redirect(detail_url)' in routes
    assert 'data-kaori-github-delete-connection' in inventory
    assert 'Configure Connection</a>' not in inventory
    assert 'asset_owner_delete_modal.render(' in detail
    assert "x-data='{ deleteModal: false" in detail
    assert "action_button.classes('critical')" in inventory
    assert 'Delete Connection' in inventory and 'Delete Connection' in modal
    assert 'def delete_connection(installation_id: int)' in routes
    assert 'provider_deletion_guard(' in routes
    assert 'if not FlaskForm().validate_on_submit():' in routes
    assert "canonical.lifecycle_status = 'retired'" in repository
    assert 'canonical.enabled = False' in repository
    assert 'IntegrationBinding.query.filter_by(integration_instance_id=canonical.id)' in repository
    assert 'db.session.delete(installation)' not in routes
    assert 'db.session.delete(canonical)' not in routes
    assert "event_type='source_control_connection_retired'" in routes
    assert "'github_source_uat.index'" in routes
    assert "IntegrationInstance.lifecycle_status == 'active'" in repository
    provider_routes = _read(
        ROOT / 'app/integrations/source_control/source_control/providers/github/application/routes.py'
    )
    assert "lifecycle_status='active'" in repository
    assert '_github_committed_connection_projection(' in provider_routes
    assert 'retire_github_connection(canonical)' in routes
