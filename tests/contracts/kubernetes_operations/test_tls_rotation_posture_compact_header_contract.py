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
    assert "xl:grid-cols-[minmax(20rem,0.72fr)_minmax(0,1.28fr)]" in template
    assert "lg:grid-cols-[minmax(14rem,1.15fr)_minmax(9rem,0.55fr)_minmax(10rem,0.65fr)_auto]" in template
    assert "xl:grid-cols-[minmax(0,1.45fr)_minmax(20rem,0.55fr)]" not in template
    assert 'neutral_metric(' not in template
