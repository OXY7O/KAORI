from pathlib import Path

import yaml


WORKFLOWS = {
    ".github/workflows/developer-check.yml": ["route"],
    ".github/workflows/publish-staging-image.yml": ["wait-for-quality"],
    ".github/workflows/deploy-staging-host.yml": ["admission"],
    ".github/workflows/telegram-github-actions.yml": ["notify", "observe-pr-failures"],
}

EXPECTED_RUNNER = ["self-hosted", "linux", "x64", "platform-ci"]


def _workflow(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def test_hosted_replacement_jobs_use_platform_ci_runner() -> None:
    for workflow_path, job_names in WORKFLOWS.items():
        workflow = _workflow(workflow_path)
        for job_name in job_names:
            assert workflow["jobs"][job_name]["runs-on"] == EXPECTED_RUNNER, (
                f"{workflow_path}:{job_name} must run on {EXPECTED_RUNNER}"
            )
