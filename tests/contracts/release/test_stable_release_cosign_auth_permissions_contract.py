from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[3] / ".github/workflows/release-image.yml"
).read_text(encoding="utf-8")


def test_cosign_can_read_the_read_only_runner_docker_config() -> None:
    assert WORKFLOW.count("--user 0:0") >= 2
    assert WORKFLOW.count("--env DOCKER_CONFIG=/root/.docker") >= 2
    assert WORKFLOW.count('--volume "$HOME/.docker:/root/.docker:ro"') >= 2
