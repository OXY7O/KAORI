import yaml


WORKFLOWS = {
    '.github/workflows/developer-check.yml': ['route'],
    '.github/workflows/publish-staging-image.yml': ['wait-for-quality'],
    '.github/workflows/deploy-staging-host.yml': ['admission'],
    '.github/workflows/telegram-github-actions.yml': ['notify', 'observe-pr-failures'],
}

EXPECTED_RUNNER = ['self-hosted', 'linux', 'x64', 'platform-ci']


def test_hosted_replacement_jobs_use_platform_ci_runner() -> None:
    for workflow_path, job_names in WORKFLOWS.items():
        with open(workflow_path, encoding='utf-8') as workflow_file:
            workflow = yaml.safe_load(workflow_file)
        for job_name in job_names:
            assert workflow['jobs'][job_name]['runs-on'] == EXPECTED_RUNNER, (
                f'{workflow_path}:{job_name} must use the platform-ci runner'
            )
