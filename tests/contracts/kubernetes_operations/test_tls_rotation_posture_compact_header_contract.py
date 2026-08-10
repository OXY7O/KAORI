from pathlib import Path


def test_tls_rotation_flow_and_posture_share_one_full_width_section() -> None:
    template = Path('app/templates/kubernetes_operations/secrets/tls_rotate.html').read_text()

    assert 'Controlled Rotation & Governance Posture' in template
    assert 'Controlled TLS Rotation Flow' in template
    assert 'TLS Certificate Posture' in template
    assert 'operational_point_flow.html' in template
    assert 'context_rail.html' not in template
    assert 'view_more_content.html' not in template
    assert 'info_flow.html' not in template
    assert 'Open Certificate Details' in template
