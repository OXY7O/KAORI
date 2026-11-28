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
    assert 'delivery.dispatched_job_execution_id' in deliveries
    assert 'delivery.payload_sha256' not in deliveries


def test_history_registries_are_scoped_server_filtered_paginated():
    runtime_source = _read(RUNTIME_PRESENTATION)
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')

    assert "JobExecution.integration_type == 'source_control'" in runtime_source
    assert '_installation_job_predicate(' in runtime_source
    assert 'integration_instance_id=installation.integration_instance_id' in runtime_source
    assert 'installation_id=installation.id' in runtime_source
    assert 'JobExecution.integration_instance_id == integration_instance_id' in runtime_source
    assert "JobExecution.job_type == 'integration_operation'" in runtime_source
    assert "JobExecution.job_type == 'source_control_repository_inventory'" in runtime_source
    assert "JobExecution.scope_type == 'integration_instance'" in runtime_source
    assert "JobExecution.scope_type == 'source_control_installation'" in runtime_source
    assert "JobExecution.scope_key == f'installation:{installation_id}'" in runtime_source
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in runtime_source
    assert "operation='runtime_refresh'" in runtime_source
    assert 'runtime_refresh_job' in runtime_source
    assert 'paginate_query(' in runtime_source
    for panel, field in ((deliveries, 'delivery_per_page'),):
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
    assert 'hx-trigger="every 15s"' not in registry
    assert 'Refresh Registry' not in registry
    assert 'github_source_uat.inventory_refresh' not in registry
    assert 'def inventory_refresh(' not in routes
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


def test_github_runtime_history_has_one_framed_evidence_workspace():
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')
    routes = _read(ROUTES)
    projection = _read(RUNTIME_PRESENTATION)

    assert not (GITHUB / 'partials/_runtime_jobs.html').exists()
    assert 'framed_tabs.render(' in runtime
    assert 'framed_tabs.render_navigation(' not in runtime
    assert 'github-runtime-evidence-registry' in runtime
    assert 'github-runtime-evidence-panel-history' in runtime
    assert 'github-runtime-evidence-panel-deliveries' in runtime
    assert "x-show=\"activeTab === 'history'\"" in runtime
    assert "x-show=\"activeTab === 'deliveries'\"" in runtime
    assert 'runtime_history_embedded=true' in runtime
    assert 'runtime_history_embedded=True' in routes
    assert 'Execution References' not in runtime
    assert 'Recent Jobs' not in runtime
    assert runtime.count('partials/_runtime_deliveries.html') == 1
    assert 'def runtime_jobs(' not in routes
    assert '/runtime/jobs' not in routes
    assert 'runtime_table_embedded' not in deliveries + routes
    assert "'runtime_view'" in runtime
    assert 'name="runtime_view" value="deliveries"' in deliveries
    assert 'class="min-w-0"' in deliveries
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in projection
    for removed in ('jobs_query', 'job_queue_options', 'job_search', 'job_pagination'):
        assert removed not in projection
    assert 'job_public_ids=_observation_job_public_ids(installation, rows)' in projection


def test_github_committed_repository_registry_is_full_width_sibling():
    decision = _read(GITHUB / 'partials/_detail_inventory.html')
    registry = _read(GITHUB / '_inventory_table.html')
    table = _read(ROOT / 'app/templates/components/table.html')

    assert 'github-inventory-lifecycle-guide' in decision
    assert decision.index('</section>\n{% if not inventory_sync_partial|default(false)') > 0
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
    assert 'framed_tabs.render(' in runtime
    assert 'framed_tabs.render_navigation(' not in runtime
    assert 'macro inventory_block_header(' in shared_table
    assert 'macro clear_filters_action(' in shared_registry
    for filename, view in (('_runtime_deliveries.html', 'deliveries'),):
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
        assert 'name="runtime_view" value="deliveries"' in page
        assert 'payload_sha256' not in page


def test_webhook_filter_controls_and_kaori_result_count():
    page = _read(GITHUB / 'partials/_runtime_deliveries.html')
    routes = _read(ROUTES)
    runtime_source = _read(RUNTIME_PRESENTATION)

    assert 'result_count=delivery_pagination.total_items' in page
    assert page.count('type="search"') == 1
    for field in ('delivery_search', 'delivery_event', 'delivery_state'):
        assert f'name="{field}"' in page
        assert f"'{field}': {field}" in page
        assert f'{field}={field}' in page
        assert f'<input type="hidden" name="{field}"' in page
    assert 'hx-trigger="change, input changed delay:400ms, submit"' in page
    assert 'registry_ui.clear_filters_action(' in page
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in runtime_source
    assert 'SourceWebhookDelivery.event_type == delivery_event' in runtime_source
    assert 'SourceWebhookDelivery.action.ilike(' in runtime_source
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


def test_webhook_history_filters_are_automatic_and_rows_are_readable():
    panel = _read(GITHUB / 'partials/_runtime_deliveries.html')
    assert 'hx-trigger="change, input changed delay:400ms, submit"' in panel
    assert 'data-kaori-canonical-registry-filter=' in panel
    assert 'registry_ui.clear_filters_action(' in panel
    assert 'Apply Filters' not in panel
    assert '<noscript>' in panel
    assert '<button type="submit"' in panel
    assert 'Filter Results' in panel
    assert 'delivery.received_at' in panel
    assert 'delivery.dispatched_job_execution_id' in panel
    assert "integration_status(delivery.processing_state, display='indicator')" in panel


def test_committed_repository_registry_uses_kaori_full_table_and_spacing():
    detail = _read(GITHUB / 'uat_detail.html')
    registry = _read(GITHUB / '_inventory_table.html')

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


def test_committed_repository_filters_preserve_installation_authority():
    routes = _read(ROUTES)
    projection = _read(ROOT / 'app/integrations/source_control/repository_inventory.py')
    registry = _read(GITHUB / '_inventory_table.html')

    assert "request.values.get('inventory_search', '').strip()[:80]" in routes
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
    repository = _read(
        ROOT / 'app/integrations/source_control/source_control/providers/github/application/repository.py'
    )
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


def test_github_detail_tab_badges_follow_runtime_and_unfiltered_committed_inventory():
    detail = _read(GITHUB / 'uat_detail.html')
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    registry = _read(GITHUB / '_inventory_table.html')
    projection = _read(RUNTIME_PRESENTATION)

    assert "('runtime', 'Runtime & History', 'activity', runtime_health_label)" in detail
    assert 'Jobs & Deliveries' not in detail
    assert "'runtime_observed': latest is not None" in projection
    assert "capability_snapshot['operation'].as_string() == 'runtime_refresh'" in projection
    assert 'github_runtime_invalidated_at' in projection
    assert 'runtime_observation_state_view(' in projection
    assert "'runtime_health_label': state['health_status_label']" in projection
    assert '{% set health = runtime_health %}' in runtime
    assert "framed_tabs.badge_oob('github', 'runtime', runtime_health_label)" in runtime
    count = "table_label.count_text(inventory.total, 'Repository', 'Repositories') if inventory.total is not none else 'Unknown'"
    assert count in detail
    assert count in registry
    assert "request.endpoint == 'github_source_uat.inventory_table'" in registry
    assert 'inventory_registry_oob|default(false)' in registry
    assert "framed_tabs.badge_oob('github', 'inventory'," in registry


def test_github_inventory_tab_count_preserves_zero_singular_plural_and_unknown():
    from jinja2 import Environment, FileSystemLoader

    environment = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    template = environment.from_string(
        "{% import 'components/table_label.html' as table_label %}"
        "{{ table_label.count_text(total, 'Repository', 'Repositories') if total is not none else 'Unknown' }}"
    )
    for total, label in ((None, 'Unknown'), (0, '0 Repositories'), (1, '1 Repository'), (2, '2 Repositories')):
        assert template.render(total=total) == label


def test_github_runtime_uses_canonical_history_and_shared_evidence():
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    routes = _read(ROUTES)
    projection = _read(RUNTIME_PRESENTATION)
    harbor = _read(ROOT / 'app/templates/integrations/registry/providers/harbor/partials/_detail_runtime.html')
    for source in (runtime, harbor):
        assert 'runtime_evidence.render(' in source
        assert 'integrations/partials/_runtime_history.html' in source
    assert "def runtime_history(installation_id: int)" in routes
    assert "runtime_history_oob=True" in routes
    assert "runtime_refresh_partial=True" in routes
    assert "runtime_history_query('source_control', str(installation.id), **scope)" in projection
    assert "'integration_instance_id': installation.integration_instance_id" in projection
    assert "'provider_key': 'github'" in projection
    assert "'adapter_key': 'github_rest_v3'" in projection
    assert "paginate_runtime_history(" in projection
    assert "runtime_history_view(" in projection
    assert "rows, pagination=pagination, job_public_ids=" in projection
    assert "'runtime_view'" in runtime
    assert 'runtime_state.diagnostics' in runtime
    assert 'hx-include="#github-runtime-history [data-kaori-runtime-history-filters] form"' in runtime
    history = _read(ROOT / 'app/templates/integrations/partials/_runtime_history.html')
    assert 'row.operation_label' in history


def test_github_runtime_observations_are_exact_scope_and_never_inferred_from_jobs():
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from flask import Flask
    from flask_login import LoginManager
    from sqlalchemy import insert

    from app.extensions.db import db
    from app.integrations.source_control.source_control.providers.github.application.runtime_presentation import (
        _runtime_observation_context,
    )
    from app.models.integration import IntegrationInstance
    from app.models.runtime import IntegrationRuntimeObservation

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite+pysqlite:///:memory:'
    app.config['SECRET_KEY'] = 'runtime-observation-test'
    login_manager = LoginManager(app)
    login_manager.user_loader(lambda _user_id: None)
    db.init_app(app)
    now = datetime.now(UTC)
    with app.test_request_context('/?per_page=5'):
        IntegrationInstance.metadata.create_all(
            bind=db.engine, tables=[IntegrationInstance.__table__, IntegrationRuntimeObservation.__table__]
        )
        for identity in (21, 22):
            db.session.execute(insert(IntegrationInstance.__table__).values(
                id=identity, name=f'GitHub {identity}', integration_type='source_control',
                provider_key='github', adapter_key='github_rest_v3', enabled=True,
                lifecycle_status='active', readiness_status='ready',
            ))

        def observation(identity, instance_id, offset, operation=None, health='healthy', provider='github'):
            snapshot = {'capabilities': [], 'metadata': {}}
            if operation:
                snapshot.update(operation=operation, job_execution_id=11)
            return IntegrationRuntimeObservation(
                integration_instance_id=identity, integration_type='source_control',
                provider_key=provider, adapter_key='github_rest_v3', instance_id=str(instance_id),
                instance_name='GitHub', trigger_type='scheduled', readiness='ready',
                health_status=health, health_score=100 if health == 'healthy' else 0,
                capability_snapshot=snapshot, diagnostics=[], observed_at=now + timedelta(minutes=offset),
            )

        db.session.add_all([
            observation(21, 7, -4),
            observation(21, 7, -3, 'full_validation'),
            observation(22, 7, -1, 'runtime_refresh'),
            observation(21, 8, -1, 'runtime_refresh'),
            observation(21, 7, -1, 'runtime_refresh', provider='other'),
        ])
        db.session.commit()
        canonical = SimpleNamespace(readiness_status='ready', metadata_json={}, last_checked_at=now)
        installation = SimpleNamespace(id=7, integration_instance_id=21, integration_instance=canonical)
        state = _runtime_observation_context(installation)
        assert state['runtime_health_label'] == 'Not Observed'
        assert state['runtime_history']['pagination']['total_items'] == 2
        assert {row['operation_label'] for row in state['runtime_history']['rows']} == {
            'Full Validation', 'Unclassified',
        }

        db.session.add(observation(21, 7, -2, 'runtime_refresh', health='unhealthy'))
        db.session.add(observation(21, 7, 0, 'full_validation'))
        db.session.commit()
        state = _runtime_observation_context(installation)
        assert state['runtime_health_label'] == 'Unhealthy'
        assert state['runtime_observation_job_id'] == 11
        assert state['runtime_history']['pagination']['total_items'] == 4

        canonical.metadata_json = {'github_runtime_invalidated_at': now.isoformat()}
        assert _runtime_observation_context(installation)['runtime_health_label'] == 'Not Observed'
        db.session.add(observation(21, 7, 1, 'runtime_refresh'))
        db.session.commit()
        assert _runtime_observation_context(installation)['runtime_health_label'] == 'Healthy'
        canonical.metadata_json = {'github_runtime_invalidated_at': 'invalid'}
        assert _runtime_observation_context(installation)['runtime_health_label'] == 'Not Observed'
        db.session.remove()
        db.engine.dispose()


def test_github_worker_observation_provenance_is_opt_in_and_not_backfilled():
    repository = _read(ROOT / 'app/integrations/runtime/repository.py')
    refresh = _read(ROOT / 'app/integrations/runtime/refresh.py')
    tasks = _read(ROOT / 'app/integrations/validation/tasks.py')
    assert "state.provider_key == 'github'" in repository
    assert "'operation': operation" in repository
    assert "'job_execution_id': job_execution_id" in repository
    assert 'operation=operation' in refresh
    assert 'job_execution_id=job_execution_id' in refresh
    assert "operation='runtime_refresh'" in tasks
    assert 'operation=operation' in tasks
    assert 'job_execution_id=job_execution_id' in tasks


def test_runtime_job_reference_is_permission_gated_and_exact_scope(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.integrations.source_control.source_control.providers.github.application import runtime_presentation

    installation = SimpleNamespace(id=7, integration_instance_id=21)
    rows = [
        SimpleNamespace(capability_snapshot={'job_execution_id': 11, 'operation': 'runtime_refresh'}),
        SimpleNamespace(capability_snapshot={'job_execution_id': 12, 'operation': 'full_validation'}),
        SimpleNamespace(capability_snapshot={'job_execution_id': 13, 'operation': 'full_validation'}),
        SimpleNamespace(capability_snapshot={'job_execution_id': 14}),
    ]
    user = SimpleNamespace(is_authenticated=True, has_permission=lambda _permission: False)
    monkeypatch.setattr(runtime_presentation, 'current_user', user)
    query = MagicMock()
    model = runtime_presentation.JobExecution
    monkeypatch.setattr(
        runtime_presentation,
        'JobExecution',
        SimpleNamespace(
            query=query,
            **{
                name: getattr(model, name)
                for name in (
                    'id', 'public_id', 'operation', 'integration_type', 'job_type',
                    'scope_type', 'scope_key', 'integration_instance_id',
                )
            },
        ),
    )
    assert runtime_presentation._observation_job_public_ids(installation, rows) == {}
    query.with_entities.assert_not_called()

    user.has_permission = lambda permission: permission == 'jobs.view'
    query.with_entities.return_value.filter.return_value.all.return_value = [
        (11, 'public-11', 'runtime_refresh'),
        (12, 'public-12', 'runtime_refresh'),
    ]
    assert runtime_presentation._observation_job_public_ids(installation, rows) == {11: 'public-11'}
    query.with_entities.return_value.filter.assert_called_once()


def test_runtime_job_navigation_reuses_canonical_registry():
    modal = _read(ROOT / 'app/templates/integrations/components/_runtime_observation_modal.html')
    routes = _read(ROOT / 'app/platform_operations/jobs/routes.py')
    presentation = _read(ROOT / 'app/platform_operations/jobs/presentation.py')
    projection = _read(RUNTIME_PRESENTATION)
    assert "current_user.has_permission('jobs.view')" in projection
    assert "JobExecution.id.in_(candidates)" in projection
    assert "candidates.get(job_id) == operation" in projection
    assert "url_for('jobs.executions', execution_tab='registry', search=row.job_execution_public_id)" in modal
    assert "row.job_execution_public_id|default(none)" in modal
    assert "@permission_required('jobs.view')" in routes
    assert 'JobExecution.public_id.ilike(value)' in presentation


def test_github_nested_runtime_tabs_preserve_outer_navigation_and_oob_target():
    runtime = _read(GITHUB / 'partials/_detail_runtime.html')
    helper = _read(ROOT / 'app/static/js/integration_workspace_tabs.js')
    history = _read(ROOT / 'app/templates/integrations/partials/_runtime_history.html')
    assert "integrationWorkspaceTabs(['history', 'deliveries'], 'history', null, 'runtime_view')" in runtime
    assert "queryKey = 'tab'" in helper
    assert 'url.searchParams.get(queryKey)' in helper
    assert 'nextUrl.searchParams.set(queryKey, tab)' in helper
    assert "if (queryKey === 'tab') nextUrl.hash = tab" in helper
    assert runtime.count("include 'integrations/partials/_runtime_history.html'") == 1
    assert runtime.count('{{ history_panel }}') == 2
    assert 'runtime_history_oob=runtime_history_oob|default(false)' in runtime
    assert 'runtime_history_embedded|default(false)' in history
    assert 'hx-swap-oob="outerHTML"' in history


def test_github_repository_sync_uses_scoped_canonical_job_poll_and_oob_inventory():
    routes = _read(ROUTES)
    inventory = _read(GITHUB / 'partials/_detail_inventory.html')
    registry = _read(GITHUB / '_inventory_table.html')
    assert "sync_job, _created = enqueue_source_repository_sync(" in routes
    assert "def synchronize_status(installation_id: int, job_id: int)" in routes
    assert "job = _repository_sync_job(installation, job_id=job_id)" in routes
    assert "job_type='source_control_repository_inventory'" in routes
    assert "operation=REPOSITORY_SYNC_OPERATION" in routes
    assert "scope_key=f'installation:{installation.id}'" in routes
    assert "scope_type='source_control_installation'" in routes
    assert "refresh_registry=job.is_terminal" in routes
    assert 'validation_poll_response(response.get_data(as_text=True), snapshot=job_snapshot(job))' in routes
    assert 'hx-post="{{ url_for(\'github_source_uat.synchronize\'' in inventory
    assert 'validation_poller.render(sync_active,' in inventory
    assert 'hx-target="#github-inventory-decision"' in inventory
    assert 'data-kaori-inventory-query-state' in registry and 'data-kaori-inventory-query-state' in inventory
    assert 'hx-swap-oob="outerHTML"' in registry
    assert 'github-posture-capabilities' in registry


def test_github_repository_detail_uses_committed_fields_and_shared_dialog():
    registry = _read(GITHUB / '_inventory_table.html')
    projection = _read(ROOT / 'app/integrations/source_control/repository_inventory.py')
    assert 'record_actions.view_more(detail_id, role=\'repository\')' in registry
    assert 'record_detail_modal.render(' in registry
    assert 'row.native_id' in registry and 'row.repository_id' in registry
    assert 'row.exact_default_branch_sha' in registry
    assert 'row.grant_valid_from' in registry and 'row.grant_observed_at' in registry
    assert 'SourceRepositoryGrant.valid_from' in projection
    assert 'SourceRepositoryGrant.last_observed_at' in projection
    assert 'SourceRepositoryGrant.installation_id == authorized_installation_id' in projection
    assert 'inventory_datetime(' in registry
    assert 'data-kaori-repository-evidence-compact' in registry
    assert 'sm:grid-cols-3' in registry
    assert 'data-kaori-repository-evidence-section="revision"' in registry
    assert 'data-kaori-repository-copy-sha' in registry
    assert 'row.exact_default_branch_sha }}</code>' in registry


def test_asset_owner_delete_confirmation_remains_shared_and_semantic():
    modal = _read(ROOT / 'app/templates/integrations/components/_asset_owner_delete_modal.html')
    assert 'role="dialog"' in modal and 'aria-modal="true"' in modal
    assert 'bg-surface-subtle' in modal
    assert 'This action cannot be undone.' in modal
    assert 'x-bind:action="deleteUrl"' in modal and 'csrf_token()' in modal
    assert '{{ scope_label }}' in modal and '{{ consequence }}' in modal
