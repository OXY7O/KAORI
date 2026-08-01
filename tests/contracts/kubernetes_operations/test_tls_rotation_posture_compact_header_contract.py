from pathlib import Path


def test_tls_rotation_posture_uses_compact_action_header():
    template = Path('app/templates/kubernetes_operations/secrets/tls_rotate.html').read_text()
    marker = "'TLS Certificate Posture'"
    start = template.index(marker)
    block = template[start:start + 400]
    assert 'compact_action=true' in block
