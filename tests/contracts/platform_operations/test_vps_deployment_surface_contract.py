from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VPS_ROOT = ROOT / 'deploy' / 'vps'
COMPOSE_OVERLAY = VPS_ROOT / 'compose.vps.yml'
DEPLOY = VPS_ROOT / 'deploy.sh'
VERIFY = VPS_ROOT / 'verify.sh'
BACKUP = VPS_ROOT / 'backup.sh'
RESTORE = VPS_ROOT / 'restore.sh'
ROLLBACK = VPS_ROOT / 'rollback.sh'
README = VPS_ROOT / 'README.md'
BASE_COMPOSE = ROOT / 'compose.production.yml'
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-uat-vps.yml'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_vps_deployment_has_a_dedicated_surface() -> None:
    for path in (COMPOSE_OVERLAY, DEPLOY, VERIFY, BACKUP, RESTORE, ROLLBACK, README):
        assert path.is_file(), f'missing VPS deployment file: {path}'

    assert not (ROOT / 'ops' / 'github-runner' / 'vps-deploy').exists()


def test_production_compose_accepts_server_side_environment_file() -> None:
    source = _read(BASE_COMPOSE)

    assert '${KAORI_ENV_FILE:-.env.production}' in source
    assert '${KAORI_IMAGE:?' in source
    assert '127.0.0.1' in source


def test_vps_overlay_keeps_state_private_persistent_and_immutable() -> None:
    source = _read(COMPOSE_OVERLAY)

    assert 'postgres:' in source
    assert 'redis:' in source
    assert '${KAORI_POSTGRES_IMAGE:?' in source
    assert '${KAORI_REDIS_IMAGE:?' in source
    assert 'kaori_vps_postgres_data' in source
    assert 'kaori_vps_redis_data' in source
    assert 'pg_isready' in source
    assert 'REDISCLI_AUTH' in source
    assert 'requirepass' in source
    assert 'ports:' not in source


def test_deploy_is_digest_pinned_fail_closed_and_ephemeral_for_registry_auth() -> None:
    source = _read(DEPLOY)

    assert source.startswith('#!/usr/bin/env bash\nset -euo pipefail\n')
    assert '@sha256:' in source
    assert 'KAORI_ENV_FILE' in source
    assert '/etc/kaori/.env.production' in source
    assert 'mktemp -d' in source
    assert 'DOCKER_CONFIG' in source
    assert 'docker login' in source
    assert '--password-stdin' in source
    assert 'trap' in source
    assert 'compose.production.yml' in source
    assert 'compose.vps.yml' in source
    assert 'run_validate' in source
    assert 'run_migrate' in source
    assert 'backup.sh' in source
    assert 'verify.sh' in source
    assert 'current-image' in source
    assert 'previous-image' in source
    assert '--pull never' in source

    assert 'StrictHostKeyChecking=no' not in source
    assert 'latest' not in source.lower()


def test_backup_restore_and_rollback_are_explicit_operator_surfaces() -> None:
    backup = _read(BACKUP)
    restore = _read(RESTORE)
    rollback = _read(ROLLBACK)

    assert 'pg_dump' in backup
    assert 'pg_restore' in restore
    assert '@sha256:' in rollback
    assert 'previous-image' in rollback
    assert '--restore-backup' in rollback
    assert 'deploy.sh' in rollback


def test_verify_checks_loopback_readiness_and_full_runtime_shape() -> None:
    source = _read(VERIFY)

    assert source.startswith('#!/usr/bin/env bash\nset -euo pipefail\n')
    assert '127.0.0.1:5000/health/ready' in source
    assert 'postgres' in source
    assert 'redis' in source
    assert 'web' in source
    assert 'worker' in source
    assert 'maintenance-worker' in source
    assert 'runtime-worker' in source
    assert 'validation-worker' in source
    assert 'analytics-worker' in source
    assert 'reports-worker' in source
    assert 'forecasting-worker' in source
    assert 'resolver-execution-worker' in source
    assert 'resolver-maintenance-worker' in source
    assert 'beat' in source
    assert 'active_queues' in source


def test_manual_vps_workflow_uses_encrypted_ssh_and_pinned_host_key() -> None:
    source = _read(WORKFLOW)

    assert 'workflow_dispatch:' in source
    assert 'candidate_tag:' in source
    assert 'KAORI_VPS_SSH_PRIVATE_KEY' in source
    assert 'KAORI_VPS_SSH_PASSPHRASE' in source
    assert 'KAORI_VPS_KNOWN_HOSTS' in source
    assert 'KAORI_VPS_HOST' in source
    assert 'KAORI_VPS_USER' in source
    assert 'KAORI_VPS_PORT' in source
    assert 'KAORI_DOCKER_REGISTRY_USERNAME' in source
    assert 'KAORI_DOCKER_REGISTRY_PASSWORD' in source
    assert 'StrictHostKeyChecking=yes' in source
    assert 'UserKnownHostsFile' in source
    assert 'scp' in source
    assert 'ssh' in source
    assert '@sha256:' in source
    assert 'publish-staging-image.yml' in source
    assert 'staging-image-' in source
    assert 'StrictHostKeyChecking=no' not in source


def test_operator_contract_keeps_real_environment_server_side() -> None:
    source = _read(README)

    assert 'deploy/vps/' in source
    assert '/etc/kaori/.env.production' in source
    assert '.env.production.example' in source
    assert '600' in source
    assert 'immutable digest' in source.lower()
    assert 'pre-migration' in source.lower()
    assert 'rollback' in source.lower()
    assert 'GitHub Secrets' in source
    assert 'ops/github-runner/' in source
