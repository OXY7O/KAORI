from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_tls_certificate_detail_uses_one_record_workspace() -> None:
    detail = (ROOT / 'app/templates/governance/tls_certificates/detail.html').read_text()

    assert 'TLS Certificate Record' in detail
    assert 'Identity &amp; Lifecycle' in detail
    assert 'Coverage &amp; Consumers' in detail
    assert 'Validity Posture' in detail
    assert 'Controlled TLS Rotation' in detail
    assert 'Certificate Identity' not in detail
    assert 'Certificate Coverage' not in detail
    assert 'detail.detail_card' not in detail
    assert detail.count(
        'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
    ) == 1


def test_tls_certificate_detail_keeps_informative_snapshot_context() -> None:
    detail = (ROOT / 'app/templates/governance/tls_certificates/detail.html').read_text()

    assert 'Common Name' in detail
    assert 'Days Remaining' in detail
    assert 'SAN Coverage' in detail
    assert 'Ingress References' in detail
    assert 'Inventory Updated' in detail
    assert 'Open TLS Rotation Workflow' in detail
