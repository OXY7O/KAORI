from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VPS_ROOT = ROOT / 'deploy' / 'vps'
BOOTSTRAP = VPS_ROOT / 'bootstrap-host.sh'
README = VPS_ROOT / 'README.md'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_vps_host_bootstrap_lives_in_deploy_surface() -> None:
    assert BOOTSTRAP.is_file(), 'deploy/vps/bootstrap-host.sh must own VPS host preparation'
    assert not (ROOT / 'ops' / 'github-runner' / 'bootstrap-vps.sh').exists()


def test_vps_host_bootstrap_accepts_only_operator_generated_rsa_public_key() -> None:
    source = _read(BOOTSTRAP)

    for marker in (
        '--ssh-public-key-file',
        'ssh-rsa ',
        'authorized_keys',
        'chmod 700',
        'chmod 600',
        'kaori-deploy',
    ):
        assert marker in source

    assert 'ssh-keygen' not in source
    assert 'PRIVATE KEY' not in source
    assert 'StrictHostKeyChecking=no' not in source


def test_vps_host_bootstrap_prepares_persistent_paths_without_overwriting_env() -> None:
    source = _read(BOOTSTRAP)

    for marker in (
        '/opt/kaori',
        '/etc/kaori/.env.production',
        '/var/lib/kaori/deploy-state',
        '/var/lib/kaori/backups',
        '.env.production.example',
        'environment file already exists; preserving',
    ):
        assert marker in source

    assert 'chmod 600 "$env_file"' in source


def test_vps_host_bootstrap_installs_and_verifies_docker_compose() -> None:
    source = _read(BOOTSTRAP)

    for marker in (
        'docker-ce',
        'docker-compose-plugin',
        'systemctl enable --now docker',
        'usermod -aG docker',
        'docker info',
        'docker compose version',
        'root-equivalent privilege',
    ):
        assert marker in source


def test_vps_runbook_documents_laptop_key_generation_and_bootstrap_sequence() -> None:
    source = _read(README)

    assert 'ssh-keygen -t rsa -b 4096' in source
    assert 'bootstrap-host.sh' in source
    assert '--ssh-public-key-file' in source
    assert 'private key' in source.lower()
    assert 'GitHub Environment' in source
