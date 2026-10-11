from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_tls_registry_uses_governance_resource_registry_pattern() -> None:
    page = _read('app/templates/kubernetes/governance/tls_certificates/partials/_page_content.html')
    scope = _read('app/templates/kubernetes/governance/tls_certificates/partials/_page_workspace.html')
    summary = _read('app/templates/kubernetes/governance/tls_certificates/partials/_summary_cards.html')
    table = _read('app/templates/kubernetes/governance/tls_certificates/partials/_table.html')
    index = _read('app/templates/kubernetes/governance/tls_certificates/index.html')

    assert 'partials/_hero.html' in page
    assert 'partials/_snapshot_context.html' in scope
    assert 'Certificate Validity' in summary
    assert 'Certificate Validity & Operations' not in summary
    assert 'partials/_sync_panel.html' not in summary
    assert 'posture_grid.render' in summary
    assert 'partials/_sync_panel.html' in scope
    assert 'components/section_intro.html' in scope
    assert "'Certificate Posture'" in scope
    assert "'Certificate Inventory'" in scope
    assert 'TLS Certificate Registry' in table
    assert 'Open Cluster Integrations' in table
    assert 'Certificate</th>' in table
    assert 'Host Coverage</th>' in table
    assert 'Ingress Usage</th>' in table
    assert 'w-full table-fixed' in table
    widths = {
        'Certificate': 27,
        'Scope': 22,
        'Validity': 12,
        'Host Coverage': 20,
        'Ingress Usage': 9,
        'Details': 10,
    }
    assert sum(widths.values()) == 100
    assert widths['Certificate'] > widths['Scope'] > widths['Host Coverage']
    assert min(widths['Certificate'], widths['Scope'], widths['Host Coverage']) > max(
        widths['Validity'], widths['Ingress Usage'], widths['Details']
    )
    for heading, width in widths.items():
        header = table.split(f'>{heading}</th>', 1)[0].rsplit('<th', 1)[-1]
        assert f'w-[{width}%]' in header
    assert 'overflow-x-auto' not in table
    assert 'min-w-[78rem]' not in table
    assert 'Current State' not in table
    assert 'Coverage State' not in table
    assert 'CN ·' in table
    assert 'Issuer ·' not in table
    assert 'hidden w-[20%]' in table
    assert 'hidden w-[9%]' in table
    assert 'resource_detail_modal.detail_button' in table
    assert "'whitespace-nowrap'" in table
    assert '<th scope="col" class="w-[10%] px-3 py-3 text-right">Details</th>' in table
    assert '<td class="px-3 py-3 text-right align-middle">' in table
    assert 'inline-flex h-9 w-9' not in table
    assert 'data-lucide="server"' in table
    assert 'Namespace · {{ record.namespace }}' in table
    assert "size='body'" not in table
    assert 'static_detail_row' not in table
    assert 'resource_detail_modal.host(' in index
    detail = _read('app/templates/kubernetes/governance/tls_certificates/partials/_detail_content.html')
    assert 'detail.header_identity_row()' in detail
    assert 'detail.header_badge_row()' not in detail


def test_tls_registry_status_and_pagination_are_canonical() -> None:
    status = _read('app/templates/kubernetes/governance/tls_certificates/partials/_status_badge.html')
    filters = _read('app/templates/kubernetes/governance/tls_certificates/partials/_filters.html')
    table = _read('app/templates/kubernetes/governance/tls_certificates/partials/_table.html')

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
    panel = _read('app/templates/kubernetes/governance/tls_certificates/partials/_sync_panel.html')
    collector = _read('app/kubernetes/governance/tls_certificates/collector.py')
    model = _read('app/models/governance.py')
    migration = _read('migrations/versions/20260731_tls_governance_evidence.py')
    detail_template = _read('app/templates/kubernetes/governance/tls_certificates/partials/_detail_content.html')

    assert "current_user.has_permission('tls_certificates.sync')" in panel
    assert "current_user.has_permission('kubernetes_secrets.bulk_rotate_tls')" in panel
    assert "current_user.has_permission('tls_certificates.bulk_update')" not in panel
    assert 'only tls.crt is accessed' in collector
    assert 'TLSCertificateCollectionState' in model
    assert 'coverage_state' in model
    assert 'tls_certificate_collection_states' in migration
    assert 'Collection &amp; Governance' in detail_template
    assert 'Inventory Updated' in detail_template
    assert 'data-kaori-tls-detail-layout="evidence-workspace-v2"' in detail_template


def test_tls_registry_condenses_redundant_evidence_copy() -> None:
    table = _read('app/templates/kubernetes/governance/tls_certificates/partials/_table.html')
    assert ' days left' in table
    assert ' days expired' in table
    assert 'title="Expires · {{ record.not_after' in table
    assert 'Coverage evidence unavailable' in table
    assert 'Host mapping evidence unavailable' not in table
    assert 'status_indicator_label(presentation.coverage_label' in table
    assert '{% elif (record.declared_host_count or 0) == 0 %}' in table
    assert 'No Declared Hosts</p>' not in table
    assert '{% if record.uncovered_hosts %}' in table
    assert '{% if (presentation.declared_host_count or 0) > 0 %}' in table
    assert 'Ingress mapping unavailable' in table
    assert 'presentation.ingress_mapping_reported' in table
    assert 'presentation.coverage_reported' in table
    assert 'resource_detail_modal.detail_button(record.id' in table
