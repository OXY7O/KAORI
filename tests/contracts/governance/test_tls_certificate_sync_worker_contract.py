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


def test_tls_manual_route_dispatches_worker_job_instead_of_collecting_inline() -> None:
    routes = (ROOT / 'app/governance/tls_certificates/routes.py').read_text()
    service = (ROOT / 'app/governance/tls_certificates/service.py').read_text()

    assert "job_key='governance.tls_certificates.sync'" in routes
    assert 'dispatch_registered_job(' in routes
    assert 'sync_tls_certificates(cluster_id)' not in routes
    assert 'def sync_tls_certificates(cluster_id:' not in service


def test_tls_page_exposes_automatic_freshness_and_worker_progress() -> None:
    template = (
        ROOT / 'app/templates/governance/tls_certificates/partials/_page_content.html'
    ).read_text()

    assert 'Automatic Sync' in template
    assert 'Last Successful' in template
    assert 'Next Scheduled' in template
    assert "payload.sync_state.is_active" in template
    assert "job_key='governance.tls_certificates.sync'" in template
