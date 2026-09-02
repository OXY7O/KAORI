from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OLD_BOOTSTRAP = ROOT / "scripts" / "bootstrap_github_runner_host.sh"
OPS_ROOT = ROOT / "ops" / "github-runner"
BOOTSTRAP = OPS_ROOT / "bootstrap-host.sh"
VERIFY = OPS_ROOT / "verify-host.sh"
HEALTH = OPS_ROOT / "runner-health.sh"
README = OPS_ROOT / "README.md"
DOCKERFILE = ROOT / "Dockerfile"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runner_host_operations_have_a_dedicated_boundary() -> None:
    assert not OLD_BOOTSTRAP.exists()
    assert BOOTSTRAP.is_file()
    assert VERIFY.is_file()
    assert HEALTH.is_file()
    assert README.is_file()


def test_bootstrap_owns_provisioning_without_embedding_verification() -> None:
    source = _read(BOOTSTRAP)

    assert source.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert 'RUNNER_VERSION="${RUNNER_VERSION:-2.328.0}"' in source
    assert "RUNNER_SHA256_X64" in source
    assert "RUNNER_SHA256_ARM64" in source
    assert "x86_64" in source
    assert "aarch64" in source
    assert "--with-runner-binary" in source
    assert "useradd" in source
    assert "docker-ce" in source
    assert "actions-runner-linux-${runner_arch}-${RUNNER_VERSION}.tar.gz" in source
    assert "sha256sum" in source

    assert "--verify-only" not in source
    assert "--verify-docker-smoke" not in source
    assert "/usr/local/sbin/kaori-runner-verify" not in source
    assert "runner-health.sh" not in source


def test_host_verifier_is_independent_read_only_and_fail_closed() -> None:
    source = _read(VERIFY)

    assert source.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "--docker-smoke" in source
    assert "systemctl" in source
    assert "docker info" in source
    assert "docker buildx version" in source
    assert "RUNNER_USER" in source
    assert "RUNNER_HOME" in source
    assert "Runner.Listener" in source
    assert "github.com" in source
    assert "x86_64" in source
    assert "aarch64" in source

    for mutation in (
        "apt-get install",
        "useradd",
        "usermod",
        "docker-ce docker-ce-cli",
        "actions-runner-linux-",
        "config.sh --token",
    ):
        assert mutation not in source


def test_runner_health_is_independent_and_non_provisioning() -> None:
    source = _read(HEALTH)

    assert source.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "docker info" in source
    assert "docker buildx version" in source
    assert "actions.runner" in source
    assert "Runner.Listener" in source
    assert "RUNNER_USER" in source

    for mutation in (
        "apt-get install",
        "useradd",
        "usermod",
        "actions-runner-linux-",
        "config.sh --token",
    ):
        assert mutation not in source


def test_operator_contract_keeps_registration_explicit() -> None:
    source = _read(README)

    assert "bootstrap-host.sh" in source
    assert "verify-host.sh" in source
    assert "runner-health.sh" in source
    assert "config.sh" in source
    assert "registration token" in source.lower()
    assert "token" not in _read(BOOTSTRAP).lower()
    assert "token" not in _read(VERIFY).lower()
    assert "token" not in _read(HEALTH).lower()


def test_production_image_does_not_copy_runner_operations_surface() -> None:
    source = _read(DOCKERFILE)
    production = source.split("FROM base AS production", maxsplit=1)[1]

    assert "ops/github-runner" not in production
    assert "COPY ops" not in production
    assert "scripts/bootstrap_github_runner_host.sh" not in production
    assert "scripts/wait_for_db.py" in production
    assert "scripts/validate_production_env.py" in production
