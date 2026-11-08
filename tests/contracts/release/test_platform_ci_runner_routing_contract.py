"""Keep runner choices aligned with trusted CI and privileged operations."""

EXPECTED_RUNNERS = {
    '.github/workflows/developer-check.yml': {
        'route': 'runs-on: ubuntu-24.04',
        'developer-check': 'runs-on: ubuntu-24.04',
        'ready-admission-guard': 'runs-on: ubuntu-24.04',
        'toolchain': 'runs-on: ubuntu-24.04',
        'python-check': 'runs-on: ubuntu-24.04',
        'validation-check': 'runs-on: ubuntu-24.04',
    },
    '.github/workflows/publish-staging-image.yml': {
        'wait-for-quality': 'runs-on: [self-hosted, linux, x64, platform-ci]',
    },
    '.github/workflows/deploy-staging-host.yml': {
        'admission': 'runs-on: [self-hosted, linux, x64, platform-ci]',
    },
    '.github/workflows/telegram-github-actions.yml': {
        'notify': 'runs-on: [self-hosted, linux, x64, platform-ci]',
        'observe-pr-failures': 'runs-on: [self-hosted, linux, x64, platform-ci]',
    },
}


def _job_block(workflow_text: str, job_name: str) -> str:
    lines = workflow_text.splitlines()
    marker = f'  {job_name}:'
    start = lines.index(marker) + 1
    block: list[str] = []
    for line in lines[start:]:
        if line.startswith('  ') and not line.startswith('    ') and line.endswith(':'):
            break
        block.append(line)
    return '\n'.join(block)


def test_ci_runner_routing_preserves_hosted_and_privileged_boundaries() -> None:
    for workflow_path, jobs in EXPECTED_RUNNERS.items():
        with open(workflow_path, encoding='utf-8') as workflow_file:
            workflow_text = workflow_file.read()
        for job_name, expected_runner in jobs.items():
            block = _job_block(workflow_text, job_name)
            runner_lines = [line.strip() for line in block.splitlines() if line.strip().startswith('runs-on:')]
            assert runner_lines == [expected_runner], (
                f'{workflow_path}:{job_name} must use {expected_runner}; got {runner_lines}'
            )
