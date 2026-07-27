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


def test_tls_worker_progress_is_owned_by_persistent_toast() -> None:
    scope = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_inventory_scope.html'
    ).read_text()
    sync_panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()
    sync_toast = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_toast.html'
    ).read_text()
    layout = (ROOT / 'app/templates/layouts/app.html').read_text()
    routes = (ROOT / 'app/governance/tls_certificates/routes.py').read_text()

    assert 'hx-trigger="every 4s"' not in scope
    assert 'hx-trigger="tlsInventorySyncFinished from:body"' in scope
    assert 'id="tls-certificates-background-refresh-trigger"' in scope
    assert 'class="htmx-indicator hidden"' in scope
    assert 'progress_bar' not in sync_panel
    assert 'TLS Secret Sync In Progress' in sync_toast
    assert 'notification-progress-indeterminate' in sync_toast
    assert "url_for('governance.tls_certificates_sync_status'" in sync_toast
    assert 'id="tls-sync-feedback"' in layout
    assert "url_for('governance.tls_certificates_active_sync')" in layout
    assert "'tlsInventorySyncFinished': True" in routes


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


def test_tls_terminal_outcomes_are_written_to_activity_audit() -> None:
    tasks = (ROOT / 'app/governance/tls_certificates/tasks.py').read_text()

    assert 'from app.models.audit import AuditEvent' in tasks
    assert 'def _record_terminal_audit(' in tasks
    assert "target_type='job_execution'" in tasks
    assert "action = f'governance_tls_secret_sync_{terminal_status}'" in tasks
    assert "terminal_status='failed'" in tasks
    assert "terminal_status='canceled'" in tasks
    assert '_record_terminal_audit(' in tasks


def test_tls_page_exposes_automatic_freshness_without_inline_worker_progress() -> None:
    sync_panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()

    assert 'Automatic Sync' in sync_panel
    assert 'Last Successful' in sync_panel
    assert 'Next Scheduled' in sync_panel
    assert "payload.sync_state.is_active" in sync_panel
    assert "job_key='governance.tls_certificates.sync'" in sync_panel
    assert 'TLS Certificate Synchronization Progress' not in sync_panel
