from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tls_sync_is_registered_and_routed_to_inventory_worker() -> None:
    definition = (ROOT / 'app/jobs/definitions/tls_certificate_sync.py').read_text()
    registry = (ROOT / 'app/jobs/registry.py').read_text()
    config = (ROOT / 'app/config/default.py').read_text()

    assert "JOB_KEY = 'governance.tls_certificates.sync'" in definition
    assert 'key=JOB_KEY' in definition
    assert "queue_name='inventory'" in definition
    assert 'TLS_CERTIFICATE_SYNC_DEFINITION' in registry
    assert "'app.governance.tls_certificates.tasks'" in config
    assert "'app.governance.tls_certificates.tasks.sync_tls_certificates'" in config
    assert "'queue': 'inventory'" in config


def test_tls_manual_route_dispatches_worker_job_instead_of_collecting_inline() -> None:
    routes = (ROOT / 'app/governance/tls_certificates/routes.py').read_text()
    service = (ROOT / 'app/governance/tls_certificates/service.py').read_text()

    assert "job_key='governance.tls_certificates.sync'" in routes
    assert 'dispatch_registered_job(' in routes
    assert 'sync_tls_certificates(cluster_id)' not in routes
    assert 'def sync_tls_certificates(cluster_id:' not in service


def test_tls_worker_progress_is_owned_by_inventory_operations_loading_bar() -> None:
    scope = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_inventory_scope.html'
    ).read_text()
    sync_panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()
    sync_response = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel_response.html'
    ).read_text()
    layout = (ROOT / 'app/templates/layouts/app.html').read_text()
    routes = (ROOT / 'app/governance/tls_certificates/routes.py').read_text()

    assert 'hx-trigger="every 4s"' not in scope
    assert 'hx-trigger="tlsInventorySyncFinished from:body"' in scope
    assert 'id="tls-certificates-background-refresh-trigger"' in scope
    assert 'class="htmx-indicator hidden"' in scope
    live_state = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_live_state.html'
    ).read_text()
    assert '{% import "components/progress_bar.html" as progress_bar %}' not in sync_panel
    assert '<progress class=' in live_state
    assert 'value="{{ payload.sync_state.progress_percent }}"' in live_state
    assert "url_for('governance.tls_certificates_sync_status'" in live_state
    assert 'payload.sync_state.progress_message' in live_state
    assert 'hx-trigger="every 1s"' in live_state
    assert 'hx-target="this"' in live_state
    assert 'hx-swap="outerHTML swap:0ms settle:0ms"' in live_state
    assert 'hx-sync="this:replace"' in live_state
    assert 'load delay:2s' not in live_state
    assert 'toast_oob=true' in sync_response
    assert 'tls-sync-feedback' not in layout
    assert "url_for('governance.tls_certificates_active_sync')" not in layout
    assert "'tlsInventorySyncFinished': True" in routes
    assert "response.headers['HX-Trigger-After-Swap']" in routes
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in routes
    assert 'feedback=feedback' in routes

def test_tls_filter_state_keeps_one_inventory_scope_boundary() -> None:
    scope = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_inventory_scope.html'
    ).read_text()
    filters = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_filters.html'
    ).read_text()
    sync_panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()
    table = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_table.html'
    ).read_text()

    assert 'id="tls-certificates-inventory-scope"' in scope
    assert "partial_mode='inventory_scope'" in scope
    assert 'hx-target="#tls-certificates-inventory-scope"' in filters
    assert 'name="partial_mode" value="inventory_scope"' in filters
    assert 'hx-target="#tls-certificates-inventory-scope"' in sync_panel
    assert table.count('hx-target="#tls-certificates-inventory-scope"') >= 3
    assert 'name="partial_mode" value="inventory_scope"' in table
    assert "partial_mode='inventory_scope'" in table


def test_tls_operation_buttons_share_the_same_kaori_component() -> None:
    sync_panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()
    action_button = (ROOT / 'app/templates/components/action_button.html').read_text()

    assert '{% import "components/action_button.html" as action_button %}' in sync_panel
    assert sync_panel.count('action_button.classes(') == 3
    assert 'Sync TLS' in sync_panel
    assert 'Configure Sync' in sync_panel
    assert 'Bulk Update' in sync_panel
    assert 'Review Active Job' not in sync_panel
    assert 'inline-flex h-10' in action_button
    assert 'rounded-lg' in action_button
    assert 'focus-visible:ring-outline-focus' in action_button


def test_tls_dispatch_attempts_are_written_to_activity_audit() -> None:
    routes = (ROOT / 'app/governance/tls_certificates/routes.py').read_text()

    assert 'from app.models.audit import AuditEvent' in routes
    assert 'def _record_dispatch_audit(' in routes
    assert "event.action = f'governance_tls_secret_sync_dispatch_{action_status}'" in routes
    assert "action_status='queued' if outcome.created else 'already_active'" in routes
    assert "action_status='quota_exceeded'" in routes
    assert "action_status='failed'" in routes
    assert "action_status='blocked'" in routes


def test_tls_terminal_outcomes_are_written_to_activity_audit() -> None:
    tasks = (ROOT / 'app/governance/tls_certificates/tasks.py').read_text()

    assert 'from app.models.audit import AuditEvent' in tasks
    assert 'def _record_terminal_audit(' in tasks
    assert "target_type='job_execution'" in tasks
    assert "action = f'governance_tls_secret_sync_{terminal_status}'" in tasks
    assert "terminal_status='failed'" in tasks
    assert "terminal_status='canceled'" in tasks
    assert '_record_terminal_audit(' in tasks


def test_tls_page_exposes_automatic_freshness_with_scoped_worker_progress() -> None:
    sync_panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()
    live_state = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_live_state.html'
    ).read_text()

    assert 'Automatic Sync' in live_state
    assert 'Last Successful' in live_state
    assert 'Next Scheduled' in live_state
    assert "payload.sync_state.is_active" in live_state
    assert "job_key='governance.tls_certificates.sync'" in sync_panel
    assert 'TLS Secret synchronization progress' in live_state
    assert 'hx-indicator="#tls-sync-panel-poll-indicator"' in live_state


def test_tls_worker_reports_granular_progress_for_single_cluster_jobs() -> None:
    tasks = (ROOT / 'app/governance/tls_certificates/tasks.py').read_text()
    collector = (ROOT / 'app/governance/tls_certificates/collector.py').read_text()
    service = (ROOT / 'app/governance/tls_certificates/service.py').read_text()

    assert 'progress_total = 100' in tasks
    assert 'def report_cluster_progress(local_percent: int, message: str)' in tasks
    assert 'progress_callback=report_cluster_progress' in tasks
    assert 'current=98' in tasks
    assert 'progress_callback: TLSProgressCallback | None = None' in collector
    assert 'Parsed {index} of {total_secrets} TLS Secrets' in collector
    assert 'progress_callback: TLSProgressCallback | None = None' in service
    assert 'Reconciled {index} of {total_records} TLS inventory records' in service
    assert "message='Finalizing TLS Secret inventory synchronization.'" in tasks


def test_tls_live_progress_polling_does_not_replace_the_whole_operations_panel() -> None:
    panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()
    live_state = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_live_state.html'
    ).read_text()
    response = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel_response.html'
    ).read_text()

    assert 'hx-trigger="every 1s"' not in panel
    assert 'hx-trigger="every 1s"' in live_state
    assert 'id="tls-sync-live-state"' in live_state
    assert '{% include "governance/tls_certificates/partials/_sync_live_state.html" %}' in response
    assert '{% include "governance/tls_certificates/partials/_sync_panel.html" %}' not in response
    assert 'notification-progress-indeterminate' not in live_state

def test_tls_sync_visibility_query_avoids_distinct_across_json_columns() -> None:
    toast = (ROOT / 'app/governance/tls_certificates/toast.py').read_text()

    assert 'JobExecution.subscribers.any(' in toast
    assert 'JobExecutionSubscriber.user_id == user_id' in toast
    assert '.outerjoin(' not in toast
    assert '.distinct()' not in toast

