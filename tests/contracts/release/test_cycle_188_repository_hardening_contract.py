from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_example_components_are_standalone_compose_stacks() -> None:
    required = (
        'example/README.md',
        'example/.env.example',
        'example/compose.demo.yml',
        'example/prometheus/compose.yml',
        'example/prometheus/prometheus.yml',
        'example/alertmanager/compose.yml',
        'example/alertmanager/alertmanager.yml',
        'example/minio/compose.yml',
        'example/thanos/compose.yml',
        'example/thanos/bucket.yml',
        'example/runner/compose.yml',
        'example/runner/README.md',
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert not missing, f'missing cycle #188 example files: {missing}'


def test_example_docs_make_standalone_authority_explicit() -> None:
    readme = _read('example/README.md')
    assert 'standalone' in readme.lower()
    for component in ('Prometheus', 'Alertmanager', 'MinIO', 'Thanos', 'Runner'):
        assert component in readme
    assert 'docker compose -f' in readme


def test_repository_front_has_branding_demo_security_and_license() -> None:
    readme = _read('README.md')
    assert 'app/static/images/kaori-logo.svg' in readme
    assert 'example/README.md' in readme
    assert 'SECURITY.md' in readme
    assert 'LICENSE' in readme
    assert 'badge.svg?branch=main' in readme
    assert (ROOT / 'LICENSE').is_file()
    assert (ROOT / 'SECURITY.md').is_file()


def test_internal_license_is_not_presented_as_open_source() -> None:
    license_text = _read('LICENSE').lower()
    assert 'internal' in license_text
    assert 'redistribution' in license_text
    assert 'commercial' in license_text
    assert 'mit license' not in license_text
    assert 'apache license' not in license_text


def test_runtime_artifact_boundary_is_application_only() -> None:
    dockerignore = _read('.dockerignore')
    assert 'example/' in dockerignore
    dockerfile = _read('Dockerfile')
    assert 'COPY . /app' not in dockerfile

    builder = _read('scripts/build_runtime_archive.sh')
    for required in ('app', 'migrations', 'run.py', 'celery_worker.py', 'gunicorn.conf.py'):
        assert required in builder
    for forbidden in ('/tests/', '/example/', '/.github/', '/docs/', '/.devcontainer/'):
        assert forbidden in builder


def test_release_authority_and_changelog_are_explicit() -> None:
    release_doc = _read('docs/releases/README.md')
    assert 'Stable Semantic Version' in release_doc
    assert 'Docker Hub' in release_doc
    assert 'immutable OCI digest' in release_doc
    assert 'without rebuilding application bits' in release_doc
    assert 'kaori-runtime-vX.Y.Z.zip' in release_doc

    changelog = _read('CHANGELOG.md')
    assert '## [Unreleased]' in changelog
    assert 'docs/releases/README.md' in changelog

    finalizer = _read('scripts/finalize_changelog.py')
    assert 'finalize_changelog' in finalizer
    assert 'invalid stable SemVer' in finalizer
    assert "UNRELEASED = '## [Unreleased]'" in finalizer


def test_terminal_and_script_ownership_standards_are_documented() -> None:
    terminal = _read('docs/engineering/TERMINAL_OUTPUT.md')
    for result in ('PASS', 'FAIL', 'SKIP', 'REUSED'):
        assert result in terminal
    assert 'Staging Acceptance' in terminal
    assert 'Production Promotion' in terminal

    scripts = _read('scripts/README.md')
    assert '`example/`' in scripts
    assert '`deploy/`' in scripts
    assert 'application lifecycle' in scripts


def test_branch_hygiene_is_ancestry_safe_and_protects_control_branches() -> None:
    workflow = _read('.github/workflows/branch-hygiene.yml')
    assert 'git merge-base --is-ancestor' in workflow
    assert 'git push origin --delete' in workflow
    for protected in ('main', 'kaori/staging', 'kaori/rc-request', 'kaori/uat-request'):
        assert protected in workflow
    assert 'kaori/tenant-*' in workflow


def test_example_configuration_contains_no_real_kaori_host() -> None:
    text = '\n'.join(path.read_text(encoding='utf-8') for path in (ROOT / 'example').rglob('*') if path.is_file())
    assert '62.171.187.206' not in text
    assert 'KAORI_HOST_SSH_PRIVATE_KEY' not in text
