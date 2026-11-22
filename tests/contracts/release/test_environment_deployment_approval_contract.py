"""Source contract for native deployment Environment approval wiring (#5081)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / '.github' / 'workflows'


def _job(workflow: str, name: str) -> str:
    lines = (WORKFLOWS / workflow).read_text(encoding='utf-8').splitlines()
    start = lines.index(f'  {name}:')
    following = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith('  ') and not lines[index].startswith('    ') and lines[index].endswith(':')
        ),
        len(lines),
    )
    return '\n'.join(lines[start:following])


def _assert_environment_before_mutation(workflow: str, job: str, env: str) -> None:
    block = _job(workflow, job)
    assert f'    environment:\n      name: {env}' in block
    assert block.index('    environment:') < block.index('    steps:')
    assert block.count('    environment:') == 1


def test_stable_publication_requires_native_production_environment() -> None:
    _assert_environment_before_mutation('release-image.yml', 'publish', 'production')
    stable = _job('release-image.yml', 'publish')
    assert 'name: Publish Stable' in stable
    assert 'needs: preflight' in stable
    assert 'contents: write' in stable


def test_rc_publication_and_uat_deploy_share_staging_environment() -> None:
    _assert_environment_before_mutation('publish-staging-image.yml', 'publish', 'staging')
    _assert_environment_before_mutation('deploy-staging-host.yml', 'deploy', 'staging')
    _assert_environment_before_mutation('reconcile-staging-publication.yml', 'reconcile', 'staging')
    assert 'environment: uat' not in (WORKFLOWS / 'deploy-staging-host.yml').read_text(encoding='utf-8')
    assert 'environment: uat' not in (WORKFLOWS / 'reconcile-staging-publication.yml').read_text(encoding='utf-8')


def test_unprivileged_admission_is_not_bound_to_production_environment() -> None:
    assert '    environment:' not in _job('release-image.yml', 'preflight')
    assert '    environment:' not in _job('publish-staging-image.yml', 'wait-for-quality')
    assert '    environment:' not in _job('deploy-staging-host.yml', 'admission')


def test_optional_runtime_inventory_is_manual_and_environment_scoped() -> None:
    workflow = (WORKFLOWS / 'environment-credential-preflight.yml').read_text(encoding='utf-8')
    script = (ROOT / 'scripts/environment-credential-preflight.sh').read_text(encoding='utf-8')

    assert 'inspect_runtime:' in workflow
    assert 'default: false' in workflow
    assert 'type: boolean' in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.inspect_runtime || false" in workflow
    assert 'environment:' in workflow
    assert 'runtime inventory requires explicit manual dispatch' in script
    assert '[[ "$GITHUB_EVENT_NAME" == workflow_dispatch ]]' in script
    assert '[[ "$GITHUB_REF" == refs/heads/main ]]' in script
    assert '[[ "$GITHUB_REF" == refs/heads/kaori/staging ]]' in script


def test_runtime_inventory_fails_closed_on_receipt_and_container_identity() -> None:
    script = (ROOT / 'scripts/environment-credential-preflight.sh').read_text(encoding='utf-8')
    inventory = script.split('if [[ "$inventory_requested" == true ]]; then', 1)[1]
    inventory = inventory.split('\nREMOTE_READ_ONLY', 1)[0]

    for key in ('KAORI_IMAGE', 'APP_VERSION', 'APP_BUILD_SHA', 'APP_BUILD_DATE'):
        assert key in inventory
    assert 'malformed or foreign immutable release receipt identity' in inventory
    assert 'receipt_image" == "$registry_image@sha256:"' in inventory
    assert 'org.opencontainers.image.revision' in inventory
    assert 'com.docker.compose.project=$project' in inventory
    assert 'com.docker.compose.service=$service' in inventory
    assert 'web instance volume differs from selected project' in inventory
    assert 'selected $service exposes a host port' in inventory
    assert 'LIMIT: observational snapshot only' in inventory


def test_runtime_inventory_is_host_read_only_without_secret_printing() -> None:
    script = (ROOT / 'scripts/environment-credential-preflight.sh').read_text(encoding='utf-8')
    remote = script.split("cat <<'REMOTE_READ_ONLY'", 1)[1].split('\nREMOTE_READ_ONLY', 1)[0]

    # Only informational Docker calls; no exec, pull, startup, migration or restore.
    for line in remote.splitlines():
        if line.lstrip().startswith('#'):
            continue
        if '$(docker ' in line or line.lstrip().startswith('docker '):
            assert any(f'docker {command}' in line for command in ('info', 'ps', 'inspect'))
    for prohibited in (
        'source "$deploy_env"',
        'cat "$deploy_env"',
        'docker exec',
        'docker pull',
        'docker restart',
        'docker compose up',
        'docker run',
        'pg_restore',
        'kubectl',
        'ssh-keyscan',
    ):
        assert prohibited not in remote


def test_runtime_inventory_remote_shell_and_negative_cases(tmp_path: Path) -> None:
    script = (ROOT / 'scripts/environment-credential-preflight.sh').read_text(encoding='utf-8')
    remote = script.split("cat <<'REMOTE_READ_ONLY'", 1)[1].split('\nREMOTE_READ_ONLY', 1)[0]
    syntax = subprocess.run(['bash', '-n'], input=remote, text=True, capture_output=True, check=False)
    assert syntax.returncode == 0, syntax.stderr

    source_sha = 'b' * 40
    root = tmp_path / 'kaori-app-audit'
    (root / 'releases' / source_sha).mkdir(parents=True)
    receipt = tmp_path / 'release.env'
    receipt.write_text(
        f"KAORI_IMAGE=docker.io/example/kaori@sha256:{'a' * 64}\n"
        'APP_VERSION=0.3.0-rc.2\n'
        f'APP_BUILD_SHA={source_sha}\n'
        'APP_BUILD_DATE=2026-11-22T00:00:00Z\n',
        encoding='utf-8',
    )
    deploy_env = tmp_path / 'deploy.env'
    deploy_env.write_text('', encoding='utf-8')
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    fake_docker = fake_bin / 'docker'
    fake_docker.write_text(
        '#!/usr/bin/env bash\ncase "$1" in\n  info|ps) exit 0 ;;\n  *) exit 87 ;;\nesac\n',
        encoding='utf-8',
    )
    fake_docker.chmod(0o700)

    env = dict(os.environ)
    env.update(
        {
            'PATH': f'{fake_bin}:{os.environ.get("PATH", "")}',
            'root': str(root),
            'receipt': str(receipt),
            'deploy_env': str(deploy_env),
            'inventory_requested': 'true',
            'registry_image': 'docker.io/example/kaori',
        }
    )
    result = subprocess.run(
        ['bash', '-c', remote],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0
    assert 'BLOCK: expected exactly one running web' in result.stderr
    assert 'PASS: configured runtime inventory' not in result.stdout

    # Duplicate identity is rejected before a Docker service is inspected.
    receipt.write_text(receipt.read_text(encoding='utf-8') + 'KAORI_IMAGE=duplicate\n', encoding='utf-8')
    duplicate = subprocess.run(
        ['bash', '-c', remote],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert duplicate.returncode != 0
    assert 'BLOCK: release receipt identity is missing or duplicated' in duplicate.stderr
