from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = ROOT / 'deploy' / 'server'
BOOTSTRAP = SERVER_ROOT / 'bootstrap-host.sh'
README = SERVER_ROOT / 'README.md'
RUNNER_README = ROOT / 'ops' / 'github-runner' / 'README.md'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_server_host_bootstrap_lives_in_deploy_surface() -> None:
    assert BOOTSTRAP.is_file(), 'deploy/server/bootstrap-host.sh must own server host preparation'
    assert not (ROOT / 'ops' / 'github-runner' / 'bootstrap-vps.sh').exists()


def test_server_host_bootstrap_accepts_only_operator_generated_rsa_public_key() -> None:
    source = _read(BOOTSTRAP)

    for marker in (
        '--ssh-public-key-file',
        'ssh-rsa[[:space:]]+',
        'authorized_keys',
        'chmod 700',
        'chmod 600',
        'kaori-deploy',
    ):
        assert marker in source

    assert 'ssh-keygen' not in source
    assert 'PRIVATE KEY' not in source
    assert 'StrictHostKeyChecking=no' not in source


def test_server_host_bootstrap_prepares_split_environment_without_overwriting_existing_files() -> None:
    source = _read(BOOTSTRAP)

    for marker in (
        '/opt/kaori',
        '/etc/kaori/app.env',
        '/etc/kaori/secrets.env',
        '/etc/kaori/deploy.env',
        '/var/lib/kaori/deploy-state',
        '/var/lib/kaori/backups',
        'deploy/env/app.env.example',
        'deploy/env/secrets.env.example',
        'deploy/env/deploy.env.example',
        'environment file already exists; preserving',
    ):
        assert marker in source

    assert 'install_env_if_missing "$app_env_template" "$app_env_file" 0640' in source
    assert 'install_env_if_missing "$secrets_env_template" "$secrets_env_file" 0600' in source
    assert 'install_env_if_missing "$deploy_env_template" "$deploy_env_file" 0640' in source
    assert '/etc/kaori/.env.production' not in source


def test_server_host_bootstrap_installs_and_verifies_docker_compose() -> None:
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


def test_server_runbook_documents_laptop_key_generation_and_bootstrap_sequence() -> None:
    source = _read(README)

    assert 'ssh-keygen -t rsa -b 4096' in source
    assert 'bootstrap-host.sh' in source
    assert '--ssh-public-key-file' in source
    assert 'private key' in source.lower()
    assert 'GitHub Environment' in source


def test_server_host_bootstrap_preserves_runner_identity_when_colocated() -> None:
    source = _read(BOOTSTRAP)

    assert "!= 'github-runner'" in source
    assert '/opt/actions-runner' in source
    assert 'preserving GitHub runner operations' in source


def test_server_runbooks_document_shared_host_without_collapsing_trust_boundary() -> None:
    deployment = _read(README)
    runner = _read(RUNNER_README)

    for marker in (
        'same physical VPS',
        'github-runner',
        'kaori-deploy',
        '/opt/actions-runner',
        '/opt/kaori',
        'SSH remains the deployment boundary',
        'temporary UAT',
    ):
        assert marker in deployment

    for marker in (
        'same physical VPS',
        '/opt/kaori',
        '/etc/kaori',
        '/var/lib/kaori',
        'deployment credentials',
    ):
        assert marker in runner
