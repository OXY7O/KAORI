from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VPS_ROOT = ROOT / 'deploy' / 'vps'
BASE_COMPOSE = ROOT / 'compose.production.yml'
VPS_COMPOSE = VPS_ROOT / 'compose.vps.yml'
DEPLOY = VPS_ROOT / 'deploy.sh'
VERIFY = VPS_ROOT / 'verify.sh'
BACKUP = VPS_ROOT / 'backup.sh'
RESTORE = VPS_ROOT / 'restore.sh'
ROLLBACK = VPS_ROOT / 'rollback.sh'
README = VPS_ROOT / 'README.md'
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-uat-vps.yml'
DOCKERFILE = ROOT / 'Dockerfile'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_vps_deployment_has_a_dedicated_deploy_boundary() -> None:
    required = (README, VPS_COMPOSE, DEPLOY, VERIFY, BACKUP, RESTORE, ROLLBACK)

    for path in required:
        assert path.is_file(), f'missing VPS deployment surface: {path.relative_to(ROOT)}'

    assert not (ROOT / 'ops' / 'github-runner' / 'vps-deploy').exists()


def test_production_compose_supports_server_side_environment_file() -> None:
    source = _read(BASE_COMPOSE)

    assert '${KAORI_ENV_FILE:-.env.production}' in source
    assert '${KAORI_IMAGE:?' in source


def test_vps_dependencies_are_private_persistent_and_immutable() -> None:
    source = _read(VPS_COMPOSE)

    assert 'postgres:' in source
    assert 'redis:' in source
    assert '${KAORI_POSTGRES_IMAGE:?' in source
    assert '${KAORI_REDIS_IMAGE:?' in source
    assert 'kaori_vps_postgres_data:' in source
    assert 'kaori_vps_redis_data:' in source
    assert '/var/lib/postgresql/data' in source
    assert '/data' in source
    assert source.count('healthcheck:') >= 2
    assert source.count('restart: unless-stopped') >= 2
    assert 'ports:' not in source


def test_uat_workflow_requires_intentional_rc_and_pinned_ssh_trust() -> None:
    source = _read(WORKFLOW)

    required = (
        'workflow_dispatch:',
        'candidate_tag:',
        'environment: uat',
        'KAORI_VPS_SSH_PRIVATE_KEY',
        'KAORI_VPS_SSH_PASSPHRASE',
        'KAORI_VPS_KNOWN_HOSTS',
        'StrictHostKeyChecking=yes',
        'UserKnownHostsFile',
        'ssh-agent',
        'SSH_ASKPASS_REQUIRE=force',
        'KAORI_DOCKER_REGISTRY_USERNAME',
        'KAORI_DOCKER_REGISTRY_PASSWORD',
        '--password-stdin',
        'staging-image-',
        'publish-staging-image.yml',
        'quality.yml',
        '@sha256:',
    )
    for marker in required:
        assert marker in source

    assert 'StrictHostKeyChecking=no' not in source
    assert '--password "${' not in source


def test_uat_workflow_resolves_evidence_before_opening_ssh() -> None:
    source = _read(WORKFLOW)

    evidence_index = source.index('staging-image-')
    ssh_index = source.index('ssh-agent')

    assert evidence_index < ssh_index
    assert 'prerelease' in source
    assert 'KAORI_IMAGE_REF' in source
    assert 'KAORI_SOURCE_SHA' in source
    assert 'KAORI_CANDIDATE_TAG' in source


def test_deploy_orders_data_safety_before_application_replacement() -> None:
    source = _read(DEPLOY)
    ordered_calls = (
        'start_dependencies',
        'wait_for_dependencies',
        'existing_database_requires_backup',
        'run_validate',
        'run_migrate',
        'start_application_services',
        'run_verify',
        'record_deployment',
    )

    positions = [source.rindex(f'\n{call}\n') for call in ordered_calls]
    assert positions == sorted(positions)
    assert 'docker build' not in source
    assert '--pull never' in source


def test_database_recovery_surfaces_are_fail_closed() -> None:
    backup = _read(BACKUP)
    restore = _read(RESTORE)
    rollback = _read(ROLLBACK)

    assert 'pg_dump' in backup
    assert '--format=custom' in backup
    assert 'chmod 0600' in backup

    assert 'readlink -f' in restore
    assert 'stop_application_services' in restore
    assert 'pg_restore' in restore
    assert '--exit-on-error' in restore

    assert 'previous_image_ref' in rollback
    assert '--restore-backup' in rollback
    assert 'backup_file' in rollback
    assert 'refusing image-only rollback' in rollback.lower()


def test_verifier_checks_full_runtime_and_single_beat() -> None:
    source = _read(VERIFY)

    for service in (
        'web',
        'worker',
        'maintenance-worker',
        'runtime-worker',
        'validation-worker',
        'analytics-worker',
        'reports-worker',
        'forecasting-worker',
        'resolver-execution-worker',
        'resolver-maintenance-worker',
        'beat',
    ):
        assert service in source

    assert '/health/ready' in source
    assert 'active_queues' in source
    assert '--restart-check' in source
    assert 'exactly one Beat' in source


def test_production_image_keeps_deployment_tooling_outside_runtime() -> None:
    dockerfile = _read(DOCKERFILE)
    production = dockerfile.split('FROM base AS production', maxsplit=1)[1]

    assert 'deploy/vps' not in production
    assert 'COPY deploy' not in production
