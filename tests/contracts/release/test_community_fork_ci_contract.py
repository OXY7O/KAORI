from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
FORK_WORKFLOW = ROOT / '.github/workflows/community-fork-check.yml'
DEVELOPER_WORKFLOW = ROOT / '.github/workflows/developer-check.yml'
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'


def test_fork_validation_uses_only_ephemeral_unprivileged_runners() -> None:
    source = FORK_WORKFLOW.read_text(encoding='utf-8')
    workflow = yaml.safe_load(source)

    assert workflow[True]['pull_request']['branches'] == ['kaori/staging']
    assert workflow['permissions'] == {'contents': 'read'}
    assert set(workflow['jobs']) == {'fork-validation'}
    job = workflow['jobs']['fork-validation']
    assert job['name'] == 'Untrusted Fork Validation'
    assert job['runs-on'] == 'ubuntu-24.04'
    assert 'head.repo.full_name != github.repository' in job['if']
    assert 'pull_request_target:' not in source
    assert 'workflow_run:' not in source
    assert 'self-hosted' not in str(job['runs-on'])
    assert 'secrets.' not in source
    assert 'GITHUB_TOKEN:' not in source

    steps = job['steps']
    checkout = steps[0]
    assert checkout['with']['ref'] == '${{ github.event.pull_request.head.sha }}'
    assert checkout['with']['persist-credentials'] is False
    assert checkout['with']['fetch-depth'] == 0
    assert all(
        'persist-credentials' not in step.get('with', {}) or step['with']['persist-credentials'] is False
        for step in steps
    )
    assert any('git diff --check' in step.get('run', '') for step in steps)
    assert any('compileall' in step.get('run', '') for step in steps)
    assert any('npm ci --ignore-scripts' in step.get('run', '') for step in steps)
    assert any('npm run check-format' in step.get('run', '') for step in steps)


def test_trusted_developer_check_and_promotion_remain_fork_closed() -> None:
    developer = yaml.safe_load(DEVELOPER_WORKFLOW.read_text(encoding='utf-8'))
    quality = yaml.safe_load(QUALITY_WORKFLOW.read_text(encoding='utf-8'))

    route = developer['jobs']['route']
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in route['if']
    assert route['runs-on'] == ['self-hosted', 'linux', 'x64', 'platform-ci']
    for name in ('toolchain', 'python-check', 'validation-check', 'developer-check'):
        assert 'route' in developer['jobs'][name]['needs']

    full_admission = developer['jobs']['full-admission']
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in full_admission['if']
    assert "needs.developer-check.result == 'success'" in full_admission['if']
    assert (
        'github.event.pull_request.head.repo.full_name == github.repository'
        in (developer['jobs']['ready-admission-guard']['if'])
    )

    profile = quality['jobs']['validation-profile']
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in profile['if']
    assert "github.head_ref == 'kaori/staging'" in profile['if']
