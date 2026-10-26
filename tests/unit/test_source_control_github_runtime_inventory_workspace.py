"""GitHub Runtime & Inventory UAT parity contracts (#3306)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITHUB = ROOT / 'app/templates/integrations/source_control/github'
ROUTES = ROOT / 'app/integrations/source_control/source_control/providers/github/application/uat_routes.py'


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
    routes = _read(ROUTES)
    jobs = _read(GITHUB / 'partials/_runtime_jobs.html')
    deliveries = _read(GITHUB / 'partials/_runtime_deliveries.html')

    assert "JobExecution.integration_type == 'source_control'" in routes
    assert 'JobExecution.integration_instance_id == installation.integration_instance_id' in routes
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in routes
    assert "operation='runtime_refresh'" in routes
    assert 'runtime_refresh_job' in routes
    assert 'paginate_query(' in routes
    for panel, field in ((jobs, 'job_per_page'), (deliveries, 'delivery_per_page')):
        assert 'data-kaori-server-filtered-registry' in panel
        assert 'components/table.html' in panel
        assert 'components/pagination.html' in panel
        assert 'components/loading_bar.html' in panel
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
    assert "inventory.total if inventory.total is not none else 'Unknown'" in registry
    assert 'exact_default_branch_sha' in registry
    assert 'revision_observed_at' in registry
    assert 'components/table.html' in registry
    assert 'components/pagination.html' in registry
    assert '[5, 10, 25, 50]' in registry
    assert 'hx-trigger="every 15s"' in registry
    assert 'read_installation_inventory(' in routes
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
    content_tabs = _read(ROOT / 'app/templates/components/content_tabs.html')

    assert 'content_tabs.render_links(' in runtime
    assert 'data-kaori-github-runtime-registry-tabs' in runtime
    assert 'id="github-runtime-evidence-registry"' in runtime
    assert "runtime_view == 'deliveries'" in runtime
    assert 'runtime_table_embedded = true' in runtime
    assert runtime.count('partials/_runtime_jobs.html') == 1
    assert runtime.count('partials/_runtime_deliveries.html') == 1
    assert 'render_links(' in content_tabs
    for page, kind in ((jobs, 'jobs'), (deliveries, 'deliveries')):
        assert f'data-kaori-runtime-registry-view="{kind}"' in page
        assert f"runtime_view='{kind}'" in page
        assert 'runtime_table_embedded|default(false)' in page
        assert 'components/pagination.html' in page
        assert 'components/loading_bar.html' in page
        assert 'data-kaori-auto-submit' in page
        assert 'registry_ui.clear_filters_action(' in page
    assert routes.count('runtime_table_embedded=True') == 2
    assert 'SourceWebhookDelivery.query.filter_by(installation_id=installation.id)' in routes


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
