WORKFLOWS = {
    '.github/workflows/developer-check.yml': ['route'],
    '.github/workflows/publish-staging-image.yml': ['wait-for-quality'],
    '.github/workflows/deploy-staging-host.yml': ['admission'],
    '.github/workflows/telegram-github-actions.yml': ['notify', 'observe-pr-failures'],
}

EXPECTED_RUNNER = 'runs-on: [self-hosted, linux, x64, platform-ci]'


def _job_block(workflow_text: str, job_name: str) -> str:
    marker = f'  {job_name}:\n'
    start = workflow_text.index(marker)
    remainder = workflow_text[start + len(marker) :]
    next_job = remainder.find('\n  ')
    if next_job == -1:
        return remainder
    return remainder[:next_job]


def test_hosted_replacement_jobs_use_platform_ci_runner() -> None:
    for workflow_path, job_names in WORKFLOWS.items():
        with open(workflow_path, encoding='utf-8') as workflow_file:
            workflow_text = workflow_file.read()
        for job_name in job_names:
            block = _job_block(workflow_text, job_name)
            assert EXPECTED_RUNNER in block, f'{workflow_path}:{job_name} must use the platform-ci runner'
