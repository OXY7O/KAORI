from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github' / 'workflows' / 'reconcile-staging-publication.yml'
SERVER_COMPOSE = ROOT / 'deploy' / 'server' / 'compose.server.yml'
UAT_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
EDGE_PUBLISH = ROOT / 'example' / 'shared-edge' / 'publish-container.sh'
EDGE_APPLY = ROOT / 'example' / 'shared-edge' / 'apply.sh'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_staging_publication_is_a_separate_post_deploy_operation() -> None:
    assert WORKFLOW.is_file()
    source = _read(WORKFLOW)
    deployment = _read(UAT_WORKFLOW)

    assert 'workflow_call:' in source
    assert 'workflow_dispatch:' in source
    assert 'push:' not in source
    assert 'Wait for Exact Staging Deployment' not in source
    assert 'environment: uat' in source
    assert 'workflow_run:' not in source

    assert 'publication-reconciliation:' in deployment
    assert 'needs: deploy' in deployment
    assert 'uses: ./.github/workflows/reconcile-staging-publication.yml' in deployment
    assert 'secrets: inherit' not in deployment
    for secret_name in (
        'KAORI_HOST_SSH_PRIVATE_KEY',
        'KAORI_HOST_SSH_PASSPHRASE',
        'KAORI_HOST_KNOWN_HOSTS',
    ):
        assert f'{secret_name}: ${{{{ secrets.{secret_name} }}}}' in deployment
        assert f'{secret_name}:' in source

    # Publication remains a separate governed stage and shared-edge ownership
    # does not leak into the application deployment or Compose authority.
    assert 'example/shared-edge' not in deployment
    assert 'edge-public' not in _read(SERVER_COMPOSE)


def test_post_deploy_reconciliation_has_no_runner_polling_cycle() -> None:
    source = _read(WORKFLOW)
    deployment = _read(UAT_WORKFLOW)

    assert 'runs-on: [self-hosted, linux, x64, kaori-ci]' in source
    assert 'sleep 15' not in source
    assert 'actions/workflows/deploy-staging-host.yml/runs' not in source

    call_job = deployment.split('  publication-reconciliation:', 1)[1]
    assert 'needs: deploy' in call_job
    assert 'uses: ./.github/workflows/reconcile-staging-publication.yml' in call_job


def test_reconciliation_reuses_existing_shared_edge_authorities() -> None:
    source = _read(WORKFLOW)

    assert '/opt/shared-edge/runtime/publish-container.sh' in source
    assert '/opt/shared-edge/runtime/apply.sh' in source
    assert 'com.docker.compose.project=kaori-production' in source
    assert 'com.docker.compose.service=web' in source
    assert '--alias kaori-web' in source
    assert '--port 5000' in source
    assert '--health-path /health/ready' in source

    # The workflow must not introduce a second edge implementation.
    assert 'docker network create edge-public' not in source
    assert 'nginx' not in source.lower()
    assert 'certbot' not in source.lower()


def test_reconciliation_requires_current_healthy_frontend_only() -> None:
    source = _read(WORKFLOW)

    assert '{{.State.Status}}' in source
    assert '{{if .State.Health}}{{.State.Health.Status}}{{end}}' in source
    assert '"$status" != \'running\'' in source
    assert '"$health" != \'healthy\'' in source
    assert 'worker' not in source
    assert 'beat' not in source.lower()
    assert 'postgres' not in source.lower()
    assert 'redis' not in source.lower()


def test_publication_failure_cannot_rewrite_application_release_state() -> None:
    source = _read(WORKFLOW)

    for forbidden in (
        'release-state.sh',
        'rollback.sh',
        'deploy.sh',
        'docker compose up',
        'REQUESTED_IMAGE',
        'REQUESTED_VERSION',
    ):
        assert forbidden not in source


def test_publish_authority_is_safe_to_repeat_for_current_binding() -> None:
    publish = _read(EDGE_PUBLISH)
    apply = _read(EDGE_APPLY)

    assert 'if [[ "$networks" == *\'"edge-public"\'* ]]' in publish
    assert 'required alias' in publish
    assert 'docker network connect --alias "$alias_name" edge-public "$container"' in publish
    assert 'bash "$SCRIPT_DIR/verify.sh" --wait-seconds 360 --renewal-dry-run' in apply


def test_reconciliation_runs_only_after_successful_deploy_job() -> None:
    deployment = _read(UAT_WORKFLOW)

    deploy_index = deployment.index('  deploy:')
    publication_index = deployment.index('  publication-reconciliation:')
    assert deploy_index < publication_index

    call_job = deployment[publication_index:]
    assert 'needs: deploy' in call_job
    assert 'uses: ./.github/workflows/reconcile-staging-publication.yml' in call_job
    assert 'secrets: inherit' not in call_job
    for secret_name in (
        'KAORI_HOST_SSH_PRIVATE_KEY',
        'KAORI_HOST_SSH_PASSPHRASE',
        'KAORI_HOST_KNOWN_HOSTS',
    ):
        assert f'{secret_name}: ${{{{ secrets.{secret_name} }}}}' in call_job
