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
RELEASE_STATE = VPS_ROOT / 'release-state.sh'
README = VPS_ROOT / 'README.md'
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
DOCKERFILE = ROOT / 'Dockerfile'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _service_block(source: str, service: str, next_service: str | None = None) -> str:
    start = source.index(f'  {service}:')
    if next_service is None:
        return source[start:]
    return source[start : source.index(f'  {next_service}:', start)]


def test_vps_deployment_has_a_dedicated_deploy_boundary() -> None:
    required = (README, VPS_COMPOSE, DEPLOY, VERIFY, BACKUP, RESTORE, ROLLBACK)

    for path in required:
        assert path.is_file(), f'missing VPS deployment surface: {path.relative_to(ROOT)}'

    assert not (ROOT / 'ops' / 'github-runner' / 'vps-deploy').exists()


def test_production_compose_supports_server_side_environment_file() -> None:
    source = _read(BASE_COMPOSE)

    assert '${KAORI_ENV_FILE:-.env.production}' in source
    assert '${KAORI_IMAGE:?' in source


def test_release_identity_is_supplied_by_governed_deployment() -> None:
    compose = _read(BASE_COMPOSE)
    deploy = _read(DEPLOY)
    workflow = _read(WORKFLOW)

    for marker in (
        'KAORI_IMAGE: ${KAORI_IMAGE:?',
        'APP_VERSION: ${APP_VERSION:?',
        'APP_BUILD_SHA: ${APP_BUILD_SHA:?',
        'APP_BUILD_DATE: ${APP_BUILD_DATE:?',
    ):
        assert marker in compose

    assert 'usage: deploy.sh IMAGE@sha256:<digest> SOURCE_SHA RELEASE_VERSION' in deploy
    for marker in (
        'export KAORI_IMAGE="$image"',
        'export APP_BUILD_SHA="$source_sha"',
        'export APP_BUILD_DATE="$image_created"',
        'candidate-release.env',
        'mv -- "$candidate_release_env" "$active_release_env"',
        'org.opencontainers.image.revision',
        '{{.Created}}',
    ):
        assert marker in deploy

    assert 'REQUESTED_VERSION:' in workflow
    assert 'requested_version=' in workflow
    assert 'bash "$deploy_script" "$requested_image" "$requested_sha" "$requested_version"' in workflow


def test_app_version_normalizes_governed_git_tag_without_v_prefix() -> None:
    deploy = _read(DEPLOY)
    release_state = _read(RELEASE_STATE)

    assert 'app_version="${release_version#v}"' in deploy
    assert 'export APP_VERSION="$app_version"' in deploy
    assert 'release_version="$(tr -d' in release_state
    assert 'APP_VERSION="${release_version#v}"' in release_state
    assert 'validate_release_identity' in release_state
    assert '${APP_VERSION:-}' in release_state
    assert '(-rc\\.[0-9]+)?$' in release_state


def test_rollback_restores_coherent_previous_release_identity() -> None:
    deploy = _read(DEPLOY)
    rollback = _read(ROLLBACK)

    assert 'current-version' in deploy
    assert 'previous-version' in deploy
    assert 'previous_version_file=' in rollback
    assert 'previous_version=' in rollback
    assert '"$previous_version"' in rollback


def test_vps_dependencies_are_private_persistent_and_immutable() -> None:
    source = _read(VPS_COMPOSE)
    postgres = _service_block(source, 'postgres', 'redis')
    redis = _service_block(source, 'redis', 'validate')
    web = _service_block(source, 'web', 'worker')
    nginx = _service_block(source, 'nginx', 'certbot')

    assert '${KAORI_POSTGRES_IMAGE:?' in postgres
    assert '${KAORI_REDIS_IMAGE:?' in redis
    assert 'kaori_vps_postgres_data:' in source
    assert 'kaori_vps_redis_data:' in source
    assert '/var/lib/postgresql/data' in postgres
    assert '/data' in redis
    assert 'healthcheck:' in postgres
    assert 'healthcheck:' in redis
    assert 'restart: unless-stopped' in postgres
    assert 'restart: unless-stopped' in redis
    assert 'ports:' not in postgres
    assert 'ports:' not in redis
    assert 'ports: !reset []' in web
    assert '"80:8080"' in nginx
    assert '"443:8443"' in nginx


def test_uat_workflow_requires_intentional_rc_and_pinned_ssh_trust() -> None:
    source = _read(WORKFLOW)

    required = (
        'workflow_dispatch:',
        'candidate_tag:',
        'environment: uat',
        'KAORI_HOST_SSH_PRIVATE_KEY',
        'KAORI_HOST_SSH_PASSPHRASE',
        'KAORI_HOST_KNOWN_HOSTS',
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


def test_uat_workflow_can_bootstrap_without_existing_on_default_branch() -> None:
    source = _read(WORKFLOW)

    assert 'push:' in source
    assert '- kaori/uat-request' in source
    assert 'refs/heads/kaori/uat-request' in source
    assert 'if [[ "$GITHUB_EVENT_NAME" == \'push\' ]]; then' in source
    assert 'releases?per_page=100' in source
    assert 'target_commitish' in source
    assert 'current_staging' in source
    assert 'workflow_dispatch:' in source
    assert 'refs/heads/kaori/staging' in source


def test_uat_workflow_resolves_evidence_before_opening_ssh() -> None:
    source = _read(WORKFLOW)

    evidence_index = source.index('staging-image-')
    ssh_index = source.index('ssh-agent')

    assert evidence_index < ssh_index
    assert 'prerelease' in source
    assert 'KAORI_IMAGE_REF' in source
    assert 'KAORI_SOURCE_SHA' in source
    assert 'KAORI_CANDIDATE_TAG' in source


def test_deploy_orders_data_safety_before_public_promotion() -> None:
    source = _read(DEPLOY)
    ordered_markers = (
        'Starting PostgreSQL and Redis',
        'Creating pre-migration PostgreSQL backup',
        'Validating portable KAORI runtime configuration',
        'Running database migrations',
        'Starting KAORI application services',
        'Internal runtime PASS',
        'Starting Compose-managed Nginx and Certbot edge',
        'mv -- "$candidate_release_env" "$active_release_env"',
    )

    positions = [source.index(marker) for marker in ordered_markers]
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
    assert '"${compose[@]}" stop "${application_services[@]}"' in restore
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
    assert 'web unexpectedly publishes a host port' in source


def test_production_image_keeps_deployment_tooling_outside_runtime() -> None:
    dockerfile = _read(DOCKERFILE)
    production = dockerfile.split('FROM base AS production', maxsplit=1)[1]

    assert 'deploy/vps' not in production
    assert 'COPY deploy' not in production
