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


def test_tls_filter_state_owns_the_same_scope_as_active_sync_polling() -> None:
    page = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_page_content.html'
    ).read_text()
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

    assert 'hx-trigger="every 4s"' not in page
    assert 'id="tls-certificates-inventory-scope"' in scope
    assert "partial_mode='inventory_scope'" in scope
    assert 'hx-indicator="#tls-certificates-sync-poll-indicator"' in scope
    assert 'id="tls-certificates-sync-poll-indicator"' in scope
    assert 'class="htmx-indicator hidden"' in scope
    assert 'hx-indicator="#tls-certificates-table-loading"' not in scope
    assert 'hx-target="#tls-certificates-inventory-scope"' in filters
    assert 'name="partial_mode" value="inventory_scope"' in filters
    assert 'hx-target="#tls-certificates-inventory-scope"' in sync_panel
    assert table.count('hx-target="#tls-certificates-inventory-scope"') >= 3
    assert 'name="partial_mode" value="inventory_scope"' in table
    assert "partial_mode='inventory_scope'" in table


def test_tls_page_exposes_automatic_freshness_and_worker_progress() -> None:
    sync_panel = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_sync_panel.html'
    ).read_text()

    assert 'Automatic Sync' in sync_panel
    assert 'Last Successful' in sync_panel
    assert 'Next Scheduled' in sync_panel
    assert "payload.sync_state.is_active" in sync_panel
    assert "job_key='governance.tls_certificates.sync'" in sync_panel
