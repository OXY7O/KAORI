from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEV_COMPOSE = ROOT / '.devcontainer' / 'compose.devcontainer.yml'
DEVCONTAINER = ROOT / '.devcontainer' / 'devcontainer.json'
ENSURE_FRONTEND = ROOT / '.devcontainer' / 'ensure-frontend.sh'
DOCKERFILE = ROOT / 'Dockerfile'
DEV_REQUIREMENTS = ROOT / 'requirements' / 'dev.txt'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def service_section(source: str, service: str) -> str:
    marker = f'  {service}:\n'
    start = source.index(marker)
    remainder = source[start + len(marker) :]
    match = re.search(r'\n  [a-z0-9][a-z0-9-]+:\n', remainder)
    return remainder if match is None else remainder[: match.start()]


def test_devcontainer_uses_isolated_project_and_survives_vscode_disconnect() -> None:
    compose = read(DEV_COMPOSE)
    config = json.loads(read(DEVCONTAINER))

    assert compose.startswith('name: kaori-dev\n')
    assert config['shutdownAction'] == 'none'
    assert 'restart: unless-stopped' in service_section(compose, 'workspace')


def test_devcontainer_starts_every_canonical_worker_and_beat() -> None:
    compose = read(DEV_COMPOSE)
    config = json.loads(read(DEVCONTAINER))
    run_services = set(config['runServices'])
    required_services = {
        'workspace',
        'db',
        'redis',
        'inventory-worker',
        'maintenance-worker',
        'validation-worker',
        'runtime-worker',
        'analytics-worker',
        'reports-worker',
        'forecasting-worker',
        'resolver-execution-worker',
        'resolver-maintenance-worker',
        'beat',
    }

    assert required_services <= run_services
    for service in required_services - {'db', 'redis'}:
        assert f'  {service}:\n' in compose

    assert 'RESOLVER_EXECUTION_CELERY_QUEUE:-resolver-execution' in compose
    assert 'RESOLVER_MAINTENANCE_CELERY_QUEUE:-resolver-maintenance' in compose


def test_devcontainer_workers_have_graceful_shutdown_windows() -> None:
    compose = read(DEV_COMPOSE)
    expected_grace_periods = {
        'inventory-worker': '45s',
        'maintenance-worker': '45s',
        'runtime-worker': '45s',
        'validation-worker': '45s',
        'analytics-worker': '180s',
        'reports-worker': '180s',
        'forecasting-worker': '300s',
        'resolver-execution-worker': '300s',
        'resolver-maintenance-worker': '45s',
        'beat': '45s',
    }

    for service, period in expected_grace_periods.items():
        section = service_section(compose, service)
        assert 'restart: unless-stopped' in section
        assert f'stop_grace_period: {period}' in section


def test_devcontainer_frontend_bootstrap_repairs_generated_output_permissions() -> None:
    source = read(ENSURE_FRONTEND)

    assert 'repair_frontend_output_permissions()' in source
    assert "'app/static/css'" in source
    assert "'app/static/fonts'" in source
    assert "'app/static/vendor'" in source
    assert 'sudo chown -R "$(id -u):$(id -g)"' in source
    assert source.rindex('repair_frontend_output_permissions') < source.index('npm run prepare-frontend')


def test_development_image_keeps_recursive_dev_requirements_available() -> None:
    dockerfile = read(DOCKERFILE)
    dev_requirements = read(DEV_REQUIREMENTS)

    assert '-r base.txt' in dev_requirements

    development = dockerfile.split('FROM base AS development', 1)[1].split(
        'FROM node:22-alpine AS frontend-build', 1
    )[0]
    assert 'COPY requirements/base.txt requirements/dev.txt /tmp/requirements/' in development
    assert 'python -m pip install -r /tmp/requirements/dev.txt' in development


def test_development_docs_define_one_canonical_compose_boundary() -> None:
    development = read(ROOT / 'docs' / 'DEVELOPMENT.md')
    running = read(ROOT / 'docs' / 'RUNNING.md')
    combined = development + '\n' + running

    assert 'kaori-dev' in combined
    assert 'shutdownAction' in combined
    assert 'docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml' in combined
    assert 'Do not use plain `docker compose down`' in combined
