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

    assert 'push:' in source
    assert '- kaori/uat-request' in source
    assert 'workflow_dispatch:' in source
    assert 'actions: read' in source
    assert 'Wait for Exact Staging Deployment' in source
    assert 'deploy-staging-host.yml' in source
    assert '.head_sha == $sha' in source
    assert "deployment_conclusion\" == 'success'" in source
    assert 'environment: uat' in source
    assert 'workflow_run:' not in source

    # Publication is deliberately outside the application deployment transaction.
    assert 'example/shared-edge' not in _read(UAT_WORKFLOW)
    assert 'edge-public' not in _read(SERVER_COMPOSE)


def test_deployment_wait_does_not_occupy_the_reconciliation_runner() -> None:
    source = _read(WORKFLOW)

    wait_job = source.split('  wait-for-deployment:', 1)[1].split('  reconcile:', 1)[0]
    reconcile_job = source.split('  reconcile:', 1)[1]

    assert 'runs-on: [self-hosted, linux, x64, platform-ci]' in wait_job
    assert 'Wait for Exact Staging Deployment' in wait_job
    assert 'runs-on: [self-hosted, linux, x64, kaori-ci]' in reconcile_job
    assert 'needs: wait-for-deployment' in reconcile_job
    assert 'Wait for Exact Staging Deployment' not in reconcile_job


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


def test_reconciliation_waits_for_exact_successful_uat_deployment_before_edge_mutation() -> None:
    source = _read(WORKFLOW)

    wait_index = source.index('Wait for Exact Staging Deployment')
    reconcile_index = source.index('Reconcile via Pinned SSH Trust')
    assert wait_index < reconcile_index
    assert 'actions/workflows/deploy-staging-host.yml/runs' in source
    assert 'branch=kaori%2Fuat-request' in source
    assert 'event=push' in source
    assert 'GITHUB_SHA' in source
    assert 'deployment_status' in source
    assert 'deployment_conclusion' in source
    assert 'Publication reconciliation blocked because exact staging deployment did not pass.' in source
    assert 'Timed out waiting for exact-SHA KAORI Staging Deployment.' in source
