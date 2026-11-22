"""Release-bound production runtime inventory source and negative contracts (#5116)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (ROOT / 'scripts/environment-credential-preflight.sh').read_text(encoding='utf-8')
WORKFLOW = (ROOT / '.github/workflows/release-image.yml').read_text(encoding='utf-8')
REMOTE = SCRIPT.split("cat <<'REMOTE_READ_ONLY'", 1)[1].split('\nREMOTE_READ_ONLY', 1)[0]


def test_manual_stable_release_checks_configured_runtime_before_registry_writes() -> None:
    events = WORKFLOW.split('on:', 1)[1].split('permissions:', 1)[0]
    publish = WORKFLOW.split('  publish:', 1)[1]
    assert 'workflow_dispatch:' in events and 'push:' not in events
    assert 'name: production' in publish
    gate = 'Verify Selected Production Runtime Against Accepted RC (Read Only)'
    assert publish.index('Recheck Release-bound Human Acceptance') < publish.index(gate)
    assert publish.index(gate) < publish.index('Log In to Docker Registry')
    assert publish.index(gate) < publish.index('Sign Stable Digest')
    assert publish.index(gate) < publish.index('Ensure Stable Tag')
    assert "TARGET_INVENTORY: 'true'" in publish
    assert "RELEASE_GATE: 'true'" in publish
    assert 'TARGET_ENV: production' in publish
    for field in ('rc_source_sha', 'rc_image_digest', 'candidate_tag', 'release_version'):
        assert '$' + '{{ needs.preflight.outputs.' + field + ' }}' in publish
    for field in (
        'REGISTRY_USER',
        'REGISTRY_PASSWORD',
        'DEPLOY_HOST',
        'DEPLOY_PORT',
        'DEPLOY_USER',
        'DEPLOY_ROOT',
        'DEPLOY_SSH_KEY',
        'DEPLOY_SSH_PASSPHRASE',
        'DEPLOY_KNOWN_HOSTS',
    ):
        assert field + ':' in publish
    assert 'bash scripts/environment-credential-preflight.sh' in publish


def test_gate_rejects_non_release_requests_before_credential_use() -> None:
    assert 'stable runtime gate requires explicit protected-main production inventory' in SCRIPT
    assert '[[ "$GITHUB_REF" == refs/heads/main ]]' in SCRIPT
    assert '[[ "$GITHUB_EVENT_NAME" == workflow_dispatch ]]' in SCRIPT
    env = dict(os.environ)
    env.update(
        {
            'RELEASE_GATE': 'true',
            'TARGET_ENV': 'staging',
            'GITHUB_REF': 'refs/heads/kaori/staging',
            'GITHUB_EVENT_NAME': 'workflow_dispatch',
            'TARGET_INVENTORY': 'true',
        }
    )
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts/environment-credential-preflight.sh')],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0
    assert 'stable runtime gate requires explicit protected-main production inventory' in result.stderr


def test_remote_gate_classifies_and_keeps_docker_read_only() -> None:
    assert 'READY_NOOP:' in REMOTE
    assert 'NEEDS_RECONCILIATION:' in REMOTE
    assert 'BLOCK:' in REMOTE
    assert '"$receipt_sha" != "$expected_rc_source_sha"' in REMOTE
    assert '"$receipt_image" != "$registry_image@$expected_rc_image_digest"' in REMOTE
    assert '"$receipt_version" != "$expected_release_version"' in REMOTE
    for item in (
        'previous-release.env',
        'previous-backup',
        'migration-result',
        'verification-result',
        'sha256sum --check --status',
    ):
        assert item in REMOTE
    syntax = subprocess.run(
        ['bash', '-n'],
        input=REMOTE,
        text=True,
        capture_output=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr
    for line in REMOTE.splitlines():
        if line.lstrip().startswith('#'):
            continue
        if '$(docker ' in line or line.lstrip().startswith('docker '):
            assert any('docker ' + verb in line for verb in ('info', 'ps', 'inspect'))
    for banned in (
        'docker exec',
        'docker pull',
        'docker restart',
        'docker compose up',
        'docker run',
        'pg_restore',
        'source "$deploy_env"',
        'cat "$deploy_env"',
    ):
        assert banned not in REMOTE


@pytest.mark.parametrize(
    'expected_field',
    ('EXPECTED_RC_SOURCE_SHA', 'EXPECTED_RC_IMAGE_DIGEST', 'EXPECTED_RELEASE_VERSION', 'EXPECTED_RC_TAG'),
)
def test_production_release_requires_all_immutable_identity_fields(expected_field: str) -> None:
    env = dict(os.environ)
    env.update(
        {
            'RELEASE_GATE': 'true',
            'TARGET_ENV': 'production',
            'GITHUB_REF': 'refs/heads/main',
            'GITHUB_EVENT_NAME': 'workflow_dispatch',
            'TARGET_INVENTORY': 'true',
            'EXPECTED_RC_SOURCE_SHA': 'a' * 40,
            'EXPECTED_RC_IMAGE_DIGEST': 'sha256:' + 'b' * 64,
            'EXPECTED_RELEASE_VERSION': '0.3.0',
            'EXPECTED_RC_TAG': 'v0.3.0-rc.3',
        }
    )
    env.pop(expected_field)
    result = subprocess.run(
        ['bash', str(ROOT / 'scripts/environment-credential-preflight.sh')],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0
    assert 'stable runtime gate requires an exact accepted RC source, tag, digest and version' in result.stderr


@pytest.fixture
def simulated_target(tmp_path: Path) -> tuple[dict[str, str], Path, Path, Path]:
    import hashlib

    source_sha = 'a' * 40
    digest = 'sha256:' + 'b' * 64
    image = 'docker.io/example/kaori@' + digest
    project = 'kaori-app-test'
    root = tmp_path / project
    (root / 'releases' / source_sha).mkdir(parents=True)
    state_root = tmp_path / 'state'
    state = state_root / 'deploy-state'
    state.mkdir(parents=True)
    backups = state_root / 'backups'
    backups.mkdir(parents=True)
    backup = backups / 'db.backup'
    backup.write_bytes(b'fixture backup')
    (backups / 'db.backup.sha256').write_text(
        hashlib.sha256(backup.read_bytes()).hexdigest() + '  ' + str(backup) + '\n',
        encoding='utf-8',
    )
    (state / 'previous-release.env').write_text('historical receipt\n', encoding='utf-8')
    (state / 'previous-backup').write_text(str(backup) + '\n', encoding='utf-8')
    for name in ('verification-result', 'migration-result'):
        (state / name).write_text('pass\n', encoding='utf-8')
    receipt = state / 'release.env'
    receipt.write_text(
        f'KAORI_IMAGE={image}\nAPP_VERSION=0.3.0\nAPP_BUILD_SHA={source_sha}\nAPP_BUILD_DATE=2026-11-22T00:00:00Z\n',
        encoding='utf-8',
    )
    deploy_env = tmp_path / 'deploy.env'
    deploy_env.write_text('', encoding='utf-8')
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    fake_docker = fake_bin / 'docker'
    fake_docker.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
case "$1" in
 info) exit 0 ;;
 ps)
   case "$*" in
     *'com.docker.compose.service=postgres'*) echo bbbbbbbbbbbb ;;
     *'com.docker.compose.service=redis'*) echo cccccccccccc ;;
     *) echo aaaaaaaaaaaa ;;
   esac ;;
 inspect)
   fmt="$3"
   cid="$4"
   case "$fmt" in
     *'.State.Status'*) echo running ;;
     *'org.opencontainers.image.revision'*) echo "$FAKE_SHA" ;;
     *'.Config.Image'*) echo "$FAKE_IMAGE" ;;
     *'.State.Health'*)
       if [[ "$cid" == bbbbbbbbbbbb && "$FAKE_DB_HEALTH" != healthy ]]; then
         echo unhealthy
       else
         echo healthy
       fi ;;
     *'.NetworkSettings.Networks'*) echo "$FAKE_PROJECT" ;;
     *'.NetworkSettings.Ports'*) echo '{}' ;;
     *'.Mounts'*)
       case "$cid" in
         bbbbbbbbbbbb) echo "$FAKE_PROJECT-postgres-data" ;;
         cccccccccccc) echo "$FAKE_PROJECT-redis-data" ;;
         *) echo "$FAKE_PROJECT-instance" ;;
       esac ;;
     *) exit 81 ;;
   esac ;;
 *) exit 82 ;;
esac
""",
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
            'registry_image': 'docker.io/example/kaori',
            'inventory_requested': 'true',
            'release_gate_requested': 'true',
            'expected_rc_source_sha': source_sha,
            'expected_rc_image_digest': digest,
            'expected_release_version': '0.3.0',
            'expected_rc_tag': 'v0.3.0-rc.3',
            'FAKE_IMAGE': image,
            'FAKE_SHA': source_sha,
            'FAKE_PROJECT': project,
            'FAKE_DB_HEALTH': 'healthy',
        }
    )
    return env, receipt, state, backup


def run_observation(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['bash', '-c', REMOTE],
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def test_matching_accepted_runtime_with_recovery_is_ready_noop(simulated_target) -> None:
    env, _receipt, _state, _backup = simulated_target
    result = run_observation(env)
    assert result.returncode == 0, result.stderr
    assert 'READY_NOOP:' in result.stdout
    assert 'PASS: configured runtime inventory' in result.stdout


@pytest.mark.parametrize('mismatch', ('source', 'digest', 'version'))
def test_target_needing_reconciliation_cannot_publish(simulated_target, mismatch: str) -> None:
    env, receipt, _state, _backup = simulated_target
    if mismatch == 'source':
        env['expected_rc_source_sha'] = 'c' * 40
    elif mismatch == 'digest':
        env['expected_rc_image_digest'] = 'sha256:' + 'd' * 64
    else:
        receipt.write_text(
            receipt.read_text(encoding='utf-8').replace('APP_VERSION=0.3.0\n', 'APP_VERSION=0.3.0-rc.3\n'),
            encoding='utf-8',
        )
    result = run_observation(env)
    assert result.returncode != 0
    assert 'NEEDS_RECONCILIATION:' in result.stderr
    assert 'READY_NOOP:' not in result.stdout


@pytest.mark.parametrize('fault', ('missing-rollback', 'missing-backup', 'wrong-checksum', 'bad-health'))
def test_broken_recovery_or_health_blocks_release(simulated_target, fault: str) -> None:
    env, _receipt, state, backup = simulated_target
    if fault == 'missing-rollback':
        (state / 'previous-release.env').unlink()
    elif fault == 'missing-backup':
        (state / 'previous-backup').unlink()
    elif fault == 'wrong-checksum':
        backup.write_bytes(b'tampered')
    else:
        env['FAKE_DB_HEALTH'] = 'unhealthy'
    result = run_observation(env)
    assert result.returncode != 0
    assert 'BLOCK:' in result.stderr
    assert 'READY_NOOP:' not in result.stdout
