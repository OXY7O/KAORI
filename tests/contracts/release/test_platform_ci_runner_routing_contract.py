from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = ROOT / '.github/workflows'
PLATFORM_RUNNER = ['self-hosted', 'linux', 'x64', 'platform-ci']
KAORI_RUNNER = ['self-hosted', 'linux', 'x64', 'kaori-ci']


def load_workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding='utf-8'))


def test_active_workflows_do_not_consume_github_hosted_ubuntu_runner() -> None:
    offenders: list[str] = []

    for path in sorted(WORKFLOW_DIR.glob('*.yml')):
        workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
        for job_name, job in workflow.get('jobs', {}).items():
            if isinstance(job, dict) and job.get('runs-on') == 'ubuntu-latest':
                offenders.append(f'{path.name}:{job_name}')

    assert offenders == [], f'GitHub-hosted runner jobs remain: {offenders}'


def test_lightweight_control_jobs_use_platform_ci_runner() -> None:
    expected = {
        'developer-check.yml': ('route',),
        'publish-staging-image.yml': ('wait-for-quality',),
        'deploy-staging-host.yml': ('admission',),
        'telegram-github-actions.yml': ('notify', 'observe-pr-failures'),
    }

    for workflow_name, job_names in expected.items():
        jobs = load_workflow(workflow_name)['jobs']
        for job_name in job_names:
            assert jobs[job_name]['runs-on'] == PLATFORM_RUNNER


def test_heavy_kaori_ci_runner_routing_is_preserved() -> None:
    developer_jobs = load_workflow('developer-check.yml')['jobs']
    quality_jobs = load_workflow('quality.yml')['jobs']
    release_jobs = load_workflow('publish-staging-image.yml')['jobs']
    deployment_jobs = load_workflow('deploy-staging-host.yml')['jobs']

    assert developer_jobs['developer-check']['runs-on'] == KAORI_RUNNER
    assert quality_jobs['validation-profile']['runs-on'] == KAORI_RUNNER
    assert quality_jobs['functional-tests']['runs-on'] == KAORI_RUNNER
    assert release_jobs['publish']['runs-on'] == KAORI_RUNNER
    assert deployment_jobs['deploy']['runs-on'] == KAORI_RUNNER
