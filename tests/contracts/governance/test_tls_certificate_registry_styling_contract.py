from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_tls_registry_uses_governance_resource_registry_pattern() -> None:
    page = _read('app/templates/governance/tls_certificates/partials/_page_content.html')
    scope = _read('app/templates/governance/tls_certificates/partials/_inventory_scope.html')
    summary = _read('app/templates/governance/tls_certificates/partials/_summary_cards.html')
    table = _read('app/templates/governance/tls_certificates/partials/_table.html')
    index = _read('app/templates/governance/tls_certificates/index.html')

    assert 'partials/_hero.html' in page
    assert 'partials/_snapshot_context.html' in scope
    assert 'Certificate Validity Posture' in summary
    assert 'posture_grid.render' in summary
    assert 'TLS Certificate Registry' in table
    assert 'Certificate</th>' in table
    assert 'Host Coverage</th>' in table
    assert 'Ingress Usage</th>' in table
    assert 'resource_detail_modal.detail_button' in table
    assert 'static_detail_row' not in table
    assert 'resource_detail_modal.host(' in index


def test_tls_registry_status_and_pagination_are_canonical() -> None:
    status = _read('app/templates/governance/tls_certificates/partials/_status_badge.html')
    filters = _read('app/templates/governance/tls_certificates/partials/_filters.html')
    table = _read('app/templates/governance/tls_certificates/partials/_table.html')

    assert "status == 'critical'" in status
    assert "status == 'expired'" in status
    assert "status in ['critical', 'expired']" not in status
    assert 'Critical Window' in status
    assert 'hx-trigger="change, keyup changed delay:500ms' in filters
    assert 'change from:select' not in filters
    assert 'Search TLS Certificates' in filters
    assert 'Rows</span>' in table
    assert "hx_swap='outerHTML'" in table
    assert "endpoint='governance.tls_certificates'" in table


def test_tls_governance_uses_canonical_permissions_and_evidence() -> None:
    panel = _read('app/templates/governance/tls_certificates/partials/_sync_panel.html')
    collector = _read('app/governance/tls_certificates/collector.py')
    model = _read('app/models/governance.py')
    migration = _read('migrations/versions/20260731_tls_governance_evidence.py')

    assert "current_user.has_permission('tls_certificates.sync')" in panel
    assert "current_user.has_permission('kubernetes_secrets.bulk_rotate_tls')" in panel
    assert "current_user.has_permission('tls_certificates.bulk_update')" not in panel
    assert 'only tls.crt is accessed' in collector
    assert 'TLSCertificateCollectionState' in model
    assert 'coverage_state' in model
    assert 'tls_certificate_collection_states' in migration
