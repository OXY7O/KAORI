from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tls_certificate_detail_uses_full_workspace_modal_content() -> None:
    page = (ROOT / 'app/templates/governance/tls_certificates/detail.html').read_text()
    detail = (ROOT / 'app/templates/governance/tls_certificates/partials/_detail_content.html').read_text()
    index = (ROOT / 'app/templates/governance/tls_certificates/index.html').read_text()

    assert 'partials/_detail_content.html' in page
    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'data-resource-detail-header' in detail
    assert 'detail.summary_strip' in detail
    assert 'Host Coverage Matrix' in detail
    assert 'Collection Evidence' in detail
    assert 'Rotation Handoff' in detail
    assert 'resource_detail_modal.host(' in index
    assert 'static_detail_row' not in detail
    assert 'detail.detail_card' in detail


def test_tls_certificate_detail_keeps_governance_boundary_and_technical_evidence() -> None:
    detail = (ROOT / 'app/templates/governance/tls_certificates/partials/_detail_content.html').read_text()

    assert 'Common Name' in detail
    assert 'Days Remaining' in detail
    assert 'Host Coverage' in detail
    assert 'Ingress Consumers' in detail
    assert 'Secret Collection' in detail
    assert 'Ingress Mapping' in detail
    assert 'Governance Snapshot Boundary' in detail
    assert 'Open TLS Rotation' in detail
    assert 'break-all font-mono' not in detail
