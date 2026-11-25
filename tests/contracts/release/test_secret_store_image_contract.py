"""Source-level OpenBao 2.7.3 candidate entrypoint contract (#5202)."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_secret_store_candidate_overrides_dev_command_and_preserves_private_mounts() -> None:
    path = ROOT / 'deploy/server/secret-store/compose.secret-store.yml'
    service = yaml.safe_load(path.read_text(encoding='utf-8'))['services']['secret-store']
    assert service['profiles'] == ['operator-bootstrap']
    assert service['command'] == ['server']
    assert service['environment'] == {'SKIP_CHOWN': '1'}
    assert 'entrypoint' not in service
    assert 'user' not in service
    assert 'ports' not in service
    assert service['cap_drop'] == ['ALL']
    assert 'no-new-privileges:true' in service['security_opt']
    mounts = {item['target']: item for item in service['volumes']}
    assert mounts['/openbao/config']['read_only'] is True
    assert mounts['/openbao/config']['bind']['create_host_path'] is False
    assert mounts['/openbao/audit']['bind']['create_host_path'] is False
