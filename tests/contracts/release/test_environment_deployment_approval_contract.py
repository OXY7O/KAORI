"""Source contract for native deployment Environment approval wiring (#5081)."""

from __future__ import annotations

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
