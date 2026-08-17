from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tls_certificate_detail_uses_compact_evidence_workspace() -> None:
    page = (ROOT / 'app/templates/kubernetes/governance/tls_certificates/detail.html').read_text()
    detail = (ROOT / 'app/templates/kubernetes/governance/tls_certificates/partials/_detail_content.html').read_text()
    index = (ROOT / 'app/templates/kubernetes/governance/tls_certificates/index.html').read_text()

    assert 'partials/_detail_content.html' in page
    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'data-kaori-tls-detail-layout="evidence-workspace-v2"' in detail
    assert 'data-resource-detail-header' in detail
    assert 'detail.header_badge_row()' in detail
    assert 'detail.summary_strip' in detail
    assert 'Certificate Identity &amp; Validity' in detail
    assert 'Coverage &amp; Consumer Evidence' in detail
    assert 'Collection &amp; Governance' in detail
    assert 'Host Coverage Matrix' in detail
    assert 'Governance Snapshot Boundary' in detail
    assert 'Open TLS Rotation' in detail
    assert 'resource_detail_modal.host(' in index
    assert 'detail.detail_card(' not in detail
    assert 'xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]' not in detail
    assert 'static_detail_row' not in detail


def test_tls_certificate_detail_keeps_governance_boundary_and_technical_evidence() -> None:
    detail = (ROOT / 'app/templates/kubernetes/governance/tls_certificates/partials/_detail_content.html').read_text()

    assert 'Common Name' in detail
    assert 'Days Remaining' in detail
    assert 'Host Coverage' in detail
    assert 'Ingress Consumers' in detail
    assert 'Secret Collection' in detail
    assert 'Ingress Mapping' in detail
    assert 'SHA-256 Fingerprint' in detail
    assert 'Certificate Identities' in detail
    assert 'Ingress Consumer Evidence Not Reported' in detail
    assert 'Governance Snapshot Boundary' in detail
    assert 'break-all font-mono' not in detail
