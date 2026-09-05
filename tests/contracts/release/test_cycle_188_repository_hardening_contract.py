from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_example_components_are_standalone_compose_stacks() -> None:
    required = (
        "example/README.md",
        "example/.env.example",
        "example/compose.demo.yml",
        "example/prometheus/compose.yml",
        "example/prometheus/prometheus.yml",
        "example/alertmanager/compose.yml",
        "example/alertmanager/alertmanager.yml",
        "example/minio/compose.yml",
        "example/thanos/compose.yml",
        "example/thanos/bucket.yml",
        "example/runner/compose.yml",
        "example/runner/README.md",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f"missing cycle #188 example files: {missing}"


def test_example_docs_make_standalone_authority_explicit() -> None:
    readme = _read("example/README.md")
    assert "standalone" in readme.lower()
    for component in ("Prometheus", "Alertmanager", "MinIO", "Thanos", "Runner"):
        assert component in readme
    assert "docker compose -f" in readme


def test_repository_front_has_branding_demo_security_and_license() -> None:
    readme = _read("README.md")
    assert "app/static/images/kaori-logo.svg" in readme
    assert "example/README.md" in readme
    assert "SECURITY.md" in readme
    assert "LICENSE" in readme
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "SECURITY.md").is_file()


def test_internal_license_is_not_presented_as_open_source() -> None:
    license_text = _read("LICENSE").lower()
    assert "internal" in license_text
    assert "redistribution" in license_text
    assert "commercial" in license_text
    assert "mit license" not in license_text
    assert "apache license" not in license_text


def test_runtime_artifact_boundary_excludes_examples() -> None:
    dockerignore = _read(".dockerignore")
    assert "example/" in dockerignore
    dockerfile = _read("Dockerfile")
    assert "COPY . /app" not in dockerfile


def test_example_configuration_contains_no_real_kaori_host() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "example").rglob("*")
        if path.is_file()
    )
    assert "62.171.187.206" not in text
    assert "kaori.cloud" not in text
    assert "KAORI_HOST_SSH_PRIVATE_KEY" not in text
