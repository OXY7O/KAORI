import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = ROOT / 'deploy' / 'server'
BASE_COMPOSE = ROOT / 'compose.production.yml'
SERVER_COMPOSE = SERVER_ROOT / 'compose.server.yml'
DEPLOY = SERVER_ROOT / 'deploy.sh'
VERIFY = SERVER_ROOT / 'verify.sh'
BACKUP = SERVER_ROOT / 'backup.sh'
RESTORE = SERVER_ROOT / 'restore.sh'
ROLLBACK = SERVER_ROOT / 'rollback.sh'
RELEASE_STATE = SERVER_ROOT / 'release-state.sh'
README = SERVER_ROOT / 'README.md'
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
DOCKERFILE = ROOT / 'Dockerfile'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _service_block(source: str, service: str, next_service: str | None = None) -> str:
    start = source.index(f'  {service}:')
    if next_service is None:
        return source[start:]
    return source[start : source.index(f'  {next_service}:', start)]


def test_server_deployment_has_a_dedicated_deploy_boundary() -> None:
    required = (README, SERVER_COMPOSE, DEPLOY, VERIFY, BACKUP, RESTORE, ROLLBACK)

    for path in required:
        assert path.is_file(), f'missing server deployment surface: {path.relative_to(ROOT)}'

    assert not (ROOT / 'deploy' / 'vps').exists()
    assert not (ROOT / 'ops' / 'github-runner' / 'server-deploy').exists()


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


def test_server_dependencies_are_private_persistent_and_immutable() -> None:
    source = _read(SERVER_COMPOSE)
    postgres = _service_block(source, 'postgres', 'redis')
    redis = _service_block(source, 'redis', 'validate')
    web = _service_block(source, 'web', 'worker')

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
    assert 'expose:' in web
    assert '- "5000"' in web
    assert 'edge-public' not in source
    assert 'edge_public' not in source
    assert '  nginx:' not in source
    assert '  certbot:' not in source


def test_server_provider_ca_trust_is_scoped_read_only_and_host_managed() -> None:
    # Keep the existing two-Compose production authority: do not introduce an
    # untracked third deployment file or a global host/DNS override.
    base = _read(BASE_COMPOSE)
    server = _read(SERVER_COMPOSE)
    bootstrap = _read(SERVER_ROOT / 'bootstrap-host.sh')
    app_env = _read(ROOT / 'deploy/env/app.env.example')
    secrets_env = _read(ROOT / 'deploy/env/secrets.env.example')
    runbook = _read(ROOT / 'docs/operations/production-provider-dns-trust.md')

    next_services = {
        'web': 'worker',
        'runtime-worker': 'validation-worker',
        'validation-worker': 'analytics-worker',
    }
    # The provider-trust CA path is exposed only to web and the two
    # integration evidence workers. Unrelated services do not inherit it.
    for service, next_service in next_services.items():
        section = _service_block(server, service, next_service)
        assert 'source: ${KAORI_TRUST_DIR:-/etc/kaori/trust}' in section, service
        assert 'target: /run/kaori/trust' in section, service
        assert 'read_only: true' in section, service
        assert 'create_host_path: false' in section, service
        assert section.count('source: ${KAORI_TRUST_DIR:-/etc/kaori/trust}') == 1

    assert server.count('source: ${KAORI_TRUST_DIR:-/etc/kaori/trust}') == len(next_services)
    assert 'kaori_production_instance:/app/instance' in base
    assert 'install -d -m 0755 /etc/kaori/trust' in bootstrap
    assert 'INTEGRATION_VAULT_ALLOWED_ORIGINS=' in app_env
    assert 'INTEGRATION_VAULT_CA_BUNDLE=' in app_env
    assert 'KAORI_LDAP_CA_BUNDLE=' in app_env
    assert 'KAORI_LDAP_BIND_PASSWORD=' not in app_env
    assert 'KAORI_LDAP_BIND_PASSWORD=' in secrets_env

    # The operational runbook must not treat a successful self-signed
    # endpoint handshake as CA:TRUE or use local DevContainer paths on hosts.
    assert 'CA:TRUE' in runbook
    assert 'keyCertSign' in runbook
    assert 'create_host_path: false' in runbook
    assert 'CoreDNS' in runbook
    assert 'rollback' in runbook


def test_host_ca_trust_preflight_precedes_database_mutation() -> None:
    deploy = _read(DEPLOY)
    bootstrap = _read(SERVER_ROOT / 'bootstrap-host.sh')
    overlay = _read(SERVER_COMPOSE)
    diagnostic = 'Host CA trust directory missing or unsafe: $KAORI_TRUST_DIR'

    assert 'if [[ ! -d "$KAORI_TRUST_DIR" || -L "$KAORI_TRUST_DIR" ]]; then' in deploy
    assert diagnostic in deploy
    assert deploy.index(diagnostic) < deploy.index('Starting PostgreSQL and Redis')
    assert deploy.index(diagnostic) < deploy.index('Creating pre-migration PostgreSQL backup')
    assert deploy.index(diagnostic) < deploy.index('Running database migrations')
    assert 'install -d -m 0755 /etc/kaori/trust' in bootstrap
    assert 'create_host_path: false' in overlay


def test_server_overlay_covers_every_canonical_app_worker_environment() -> None:
    base = _read(BASE_COMPOSE)
    overlay = _read(SERVER_COMPOSE)
    base_service_block = base.split('services:\n', maxsplit=1)[1].split('\nvolumes:', maxsplit=1)[0]
    canonical_services = re.findall(r'^  ([a-z][a-z0-9-]*):$', base_service_block, re.MULTILINE)
    application_services = [
        service for service in canonical_services if service not in {'postgres', 'redis', 'validate', 'migrate'}
    ]

    assert 'registry-security-worker' in application_services
    for service in application_services:
        pattern = rf'^  {re.escape(service)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|^volumes:|\Z)'
        match = re.search(pattern, overlay, re.MULTILINE | re.DOTALL)
        assert match is not None, f'missing production server overlay for {service}'
        block = match.group(1)
        assert 'env_file: !override' in block, f'{service} must replace legacy .env.production'
        for authority in ('KAORI_APP_ENV_FILE', 'KAORI_SECRETS_ENV_FILE', 'KAORI_RELEASE_ENV_FILE'):
            assert authority in block, f'{service} is missing {authority}'

    for script in (DEPLOY, VERIFY, RESTORE):
        contents = _read(script)
        for service in application_services:
            assert service in contents, f'{script.name} omits application service {service}'


def test_uat_workflow_requires_intentional_rc_and_pinned_ssh_trust() -> None:
    source = _read(WORKFLOW)

    required = (
        'workflow_dispatch:',
        'candidate_tag:',
        'environment:\n      name: staging',
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


def test_deploy_orders_data_safety_before_committing_application_release() -> None:
    source = _read(DEPLOY)
    ordered_markers = (
        'Starting PostgreSQL and Redis',
        'Creating pre-migration PostgreSQL backup',
        'Validating portable KAORI runtime configuration',
        'Running database migrations',
        'Starting KAORI application services',
        'Internal runtime PASS',
        'KAORI application runtime healthy',
        'mv -- "$candidate_release_env" "$active_release_env"',
    )

    positions = [source.index(marker) for marker in ordered_markers]
    assert positions == sorted(positions)
    assert 'docker build' not in source
    assert '--pull never' in source
    assert '--remove-orphans' not in source
    assert 'public HTTPS readiness' not in source
    assert 'edge-public' not in source


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
        'registry-security-worker',
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


def _validate_celery_worker_response(
    payload: str, *, expected: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    source = _read(VERIFY)
    prefix = """docker exec -i "$probe_cid" python -c '"""
    script = source.split(prefix + '\n', 1)[1].split('\n\' "$destination_csv"', 1)[0]
    workers = [
        'worker',
        'registry-security-worker',
        'maintenance-worker',
        'runtime-worker',
        'validation-worker',
        'analytics-worker',
        'reports-worker',
        'forecasting-worker',
        'resolver-execution-worker',
        'resolver-maintenance-worker',
    ]
    names = expected if expected is not None else [f'celery@worker-{n}' for n in range(10)]
    return subprocess.run(
        [sys.executable, '-c', script, ','.join(names), ','.join(workers)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )


def test_celery_worker_readiness_checks_all_nodes_using_one_targeted_inspect() -> None:
    source = _read(VERIFY)
    assert source.count(' active_queues 2>/dev/null') == 1
    assert '--destination="$destination_csv"' in source
    assert '--json --timeout=20' in source
    assert 'docker inspect --format' in source
    assert 'worker) node_prefix=inventory' in source
    assert 'registry-security-worker) node_prefix=registry-security' in source
    assert 'reports-worker) node_prefix=reports' in source
    assert 'Beat PASS' in source
    assert 'server_database_boundary.py runtime' in source
    assert '/health/ready' in source
    assert '--restart-check' in source


def test_celery_worker_readiness_positive_and_negative_response_contracts() -> None:
    names = [f'celery@worker-{n}' for n in range(10)]
    valid = {name: [{'name': 'queue', 'routing_key': 'queue'}] for name in names}
    assert _validate_celery_worker_response(json.dumps(valid)).returncode == 0

    missing = valid.copy()
    del missing[names[4]]
    result = _validate_celery_worker_response(json.dumps(missing))
    assert result.returncode != 0
    assert 'validation-worker did not report active queues' in result.stderr

    empty = {**valid, names[2]: []}
    assert _validate_celery_worker_response(json.dumps(empty)).returncode != 0
    invalid_queue = {**valid, names[3]: [{'no_name': 'value'}]}
    assert _validate_celery_worker_response(json.dumps(invalid_queue)).returncode != 0
    assert _validate_celery_worker_response('not-json').returncode != 0
    assert _validate_celery_worker_response('[]').returncode != 0
    assert _validate_celery_worker_response(json.dumps(valid), expected=[names[0]] * 10).returncode != 0


def test_production_image_keeps_deployment_tooling_outside_runtime() -> None:
    dockerfile = _read(DOCKERFILE)
    production = dockerfile.split('FROM base AS production', maxsplit=1)[1]

    assert 'deploy/server' not in production
    assert 'deploy/vps' not in production
    assert 'COPY deploy' not in production


def test_rollback_requires_complete_previous_release_lineage_and_reviewed_backup() -> None:
    rollback = _read(ROLLBACK)

    for marker in (
        'previous-image',
        'previous-source-sha',
        'previous-version',
        'previous-backup',
        'recorded previous image is not immutable',
        'recorded previous source SHA is invalid',
        'recorded previous release version is invalid',
        'recorded rollback backup does not exist',
        'restore.sh" "$backup_file"',
        'deploy.sh" "$previous_image_ref" "$previous_source_sha" "$previous_version"',
    ):
        assert marker in rollback


def test_deployment_commits_release_state_only_after_runtime_verification() -> None:
    deploy = _read(DEPLOY)

    runtime_verified = deploy.index("status '✅' 'Internal runtime PASS'")
    current_image = deploy.index('printf \'%s\\n\' "$image" > "$KAORI_STATE_DIR/current-image"')
    active_release = deploy.index('mv -- "$candidate_release_env" "$active_release_env"')

    assert runtime_verified < current_image < active_release
    assert 'committed=false' in deploy
    assert '[[ "$committed" == \'true\' ]] || rm -f -- "$candidate_release_env"' in deploy


def test_expanded_uat_deployment_steps_expose_immutable_evidence_and_host_phases() -> None:
    workflow = _read(WORKFLOW)
    deploy = _read(DEPLOY)
    backup = _read(BACKUP)
    verify = _read(VERIFY)

    for marker in (
        'UAT release evidence · resolving current accepted staging SHA',
        'UAT release evidence · staging Full Admission PASS',
        'UAT release evidence · immutable image digest, RC and source pinned',
        'UAT host · preparing ephemeral SSH credentials',
        'UAT host · deployment source artifacts transferred',
        'UAT host · starting governed deploy.sh',
        'UAT host · governed deployment script completed',
        'Public-edge reconciliation and human UAT acceptance remain separate',
    ):
        assert marker in workflow

    assert workflow.index('UAT host · deployment source artifacts transferred') < workflow.index(
        'UAT host · starting governed deploy.sh'
    )
    assert "printf 'registry_password=%q\\n'" in workflow
    assert 'bash "$deploy_script" "$requested_image" "$requested_sha" "$requested_version"' in workflow

    for marker in (
        'UAT host deployment · validating immutable release',
        'UAT host deployment · recording verified immutable release state',
        'Verified release state committed',
        'Host deployment elapsed',
    ):
        assert marker in deploy
    assert deploy.index("status '✅' 'Internal runtime PASS'") < deploy.index(
        'UAT host deployment · recording verified immutable release state'
    )

    # The backup command substitution still receives exactly one stdout path:
    # phase logs go to stderr, never dump private PostgreSQL role inventory.
    assert 'backup_path="$(bash "$SCRIPT_DIR/backup.sh")"' in deploy
    assert 'UAT backup · archive, schema and role checksum evidence PASS' in backup
    for line in backup.splitlines():
        if 'printf ' in line and 'UAT backup ·' in line:
            assert '>&2' in line

    assert 'UAT verification · checking exact Beat count' in verify
    assert 'UAT verification · checking effective PostgreSQL access' in verify
    assert 'UAT verification · probing internal web readiness' in verify
    assert "printf '🩺 Internal web:5000 readiness PASS" in verify

# Environment-configured runtime target selection: no slot-count mode.
_TARGET_KEYS = (
    'KAORI_COMPOSE_PROJECT',
    'KAORI_NETWORK_NAME',
    'KAORI_INSTANCE_VOLUME',
    'KAORI_POSTGRES_VOLUME',
    'KAORI_REDIS_VOLUME',
    'KAORI_STATE_DIR',
    'KAORI_BACKUP_DIR',
    'KAORI_ACTIVE_RELEASE_ENV_FILE',
    'KAORI_DEPLOY_ENV_FILE',
    'KAORI_APP_ENV_FILE',
    'KAORI_SECRETS_ENV_FILE',
    'KAORI_POSTGRES_ADMIN_ENV_FILE',
    'KAORI_POSTGRES_MIGRATION_ENV_FILE',
    'KAORI_TRUST_DIR',
    'KAORI_DEPLOY_ROOT',
    'COMPOSE_PROJECT_NAME',
)


def _runtime_target_contract(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key not in _TARGET_KEYS}
    env.update(overrides)
    return subprocess.run(
        ['bash', '-c', 'source "$1"; kaori_validate_target_config', 'bash', str(RELEASE_STATE)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_existing_runtime_identity_remains_the_default() -> None:
    result = _runtime_target_contract({})
    assert result.returncode == 0, result.stderr
    compose = _read(BASE_COMPOSE)
    overlay = _read(SERVER_COMPOSE)
    assert 'name: ${KAORI_COMPOSE_PROJECT:-kaori-production}' in compose
    assert 'name: ${KAORI_NETWORK_NAME:-kaori-production}' in compose
    assert 'name: ${KAORI_INSTANCE_VOLUME:-kaori-production-instance}' in compose
    assert 'name: ${KAORI_POSTGRES_VOLUME:-kaori-vps-postgres-data}' in overlay
    assert 'name: ${KAORI_REDIS_VOLUME:-kaori-vps-redis-data}' in overlay


def _distinct_target(project: str = 'kaori-app-blue') -> dict[str, str]:
    config = f'/etc/kaori/targets/{project}'
    state = f'/var/lib/kaori/targets/{project}'
    return {
        'KAORI_COMPOSE_PROJECT': project,
        'KAORI_NETWORK_NAME': project,
        'KAORI_INSTANCE_VOLUME': f'{project}-instance',
        'KAORI_POSTGRES_VOLUME': f'{project}-postgres-data',
        'KAORI_REDIS_VOLUME': f'{project}-redis-data',
        'KAORI_STATE_DIR': f'{state}/deploy-state',
        'KAORI_BACKUP_DIR': f'{state}/backups',
        'KAORI_ACTIVE_RELEASE_ENV_FILE': f'{state}/deploy-state/release.env',
        'KAORI_DEPLOY_ENV_FILE': f'{config}/deploy.env',
        'KAORI_APP_ENV_FILE': f'{config}/app.env',
        'KAORI_SECRETS_ENV_FILE': f'{config}/secrets.env',
        'KAORI_POSTGRES_ADMIN_ENV_FILE': f'{config}/postgres-admin.env',
        'KAORI_POSTGRES_MIGRATION_ENV_FILE': f'{config}/postgres-migrate.env',
        'KAORI_TRUST_DIR': f'{config}/trust',
        'KAORI_DEPLOY_ROOT': f'/opt/kaori/targets/{project}',
    }


def test_distinct_runtime_identity_is_configuration_not_host_count() -> None:
    result = _runtime_target_contract(_distinct_target())
    assert result.returncode == 0, result.stderr

    # Same host/IP does not merge distinct Compose and state identities.
    for key, value in (
        ('KAORI_POSTGRES_VOLUME', 'kaori-vps-postgres-data'),
        ('KAORI_INSTANCE_VOLUME', 'kaori-production-instance'),
        ('KAORI_STATE_DIR', '/var/lib/kaori/deploy-state'),
        ('KAORI_BACKUP_DIR', '/var/lib/kaori/backups'),
        ('KAORI_DEPLOY_ROOT', '/opt/kaori'),
    ):
        bad = {**_distinct_target(), key: value}
        assert _runtime_target_contract(bad).returncode != 0, key


def test_runtime_target_rejects_foreign_projects_and_conflicts() -> None:
    for project in ('kaori-website', 'kaori-docs', '../kaori-app', 'kaori-app-'):
        assert _runtime_target_contract(_distinct_target(project)).returncode != 0, project
    assert _runtime_target_contract({'KAORI_POSTGRES_VOLUME': 'kaori-app-blue-postgres-data'}).returncode != 0
    assert _runtime_target_contract({'COMPOSE_PROJECT_NAME': 'another-project'}).returncode != 0


def test_staging_environment_selects_configured_target_and_owns_edge_boundary() -> None:
    deploy = _read(WORKFLOW)
    publish = _read(ROOT / '.github/workflows/reconcile-staging-publication.yml')
    assert 'environment:\n      name: staging' in deploy
    assert 'KAORI_HOST_DEPLOY_ENV_FILE: ' in deploy
    assert 'KAORI_DEPLOY_ENV_FILE="$deploy_env" KAORI_DEPLOY_ROOT="$deploy_root"' in deploy
    assert 'Distinct Application target requires separate operator-approved ingress.' in publish
    assert 'Refusing canonical public-edge mutation for a distinct Compose runtime.' in publish
