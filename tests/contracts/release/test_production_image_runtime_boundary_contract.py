from pathlib import Path

DOCKERFILE = Path('Dockerfile')


def _production_stage() -> str:
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')
    return dockerfile.split('FROM base AS production', maxsplit=1)[1]


def test_production_stage_forbids_repository_wide_copy() -> None:
    production = _production_stage()

    assert 'COPY --chown=kaori:kaori . /app' not in production
    assert 'COPY . /app' not in production


def test_production_stage_uses_explicit_runtime_allowlist() -> None:
    production = _production_stage()

    expected_copy_contracts = (
        'COPY --chown=kaori:kaori app /app/app',
        'COPY --chown=kaori:kaori migrations /app/migrations',
        'COPY --chown=kaori:kaori run.py celery_worker.py gunicorn.conf.py /app/',
        'COPY --chown=kaori:kaori \\\n    scripts/wait_for_db.py \\\n    scripts/validate_production_env.py \\\n    /app/scripts/',
    )

    for expected in expected_copy_contracts:
        assert expected in production


def test_production_stage_does_not_copy_development_or_governance_surfaces() -> None:
    production = _production_stage()
    production_copy_lines = '\n'.join(
        line.strip() for line in production.splitlines() if line.lstrip().startswith('COPY ')
    )

    forbidden_sources = (
        'tests',
        'docs',
        '.github',
        '.devcontainer',
        '.vscode',
        'deploy',
        'frontend',
        'package.json',
        'package-lock.json',
        'pyproject.toml',
        'pytest.ini',
    )

    for forbidden in forbidden_sources:
        assert forbidden not in production_copy_lines


def test_base_stage_removes_python_requirement_manifest_after_install() -> None:
    dockerfile = DOCKERFILE.read_text(encoding='utf-8')
    base_stage = dockerfile.split('FROM base AS development', maxsplit=1)[0]

    assert 'rm -f /tmp/requirements/base.txt' in base_stage
