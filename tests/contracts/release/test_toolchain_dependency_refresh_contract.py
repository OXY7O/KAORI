import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NODE_VERSION = '22.23.2'
NPM_VERSION = '10.9.9'
PYRIGHT_VERSION = '1.1.414'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_node_and_npm_toolchain_is_exact_and_aligned() -> None:
    dockerfile = read('Dockerfile')
    ci_dockerfile = read('.github/ci/Dockerfile')
    devcontainer = json.loads(read('.devcontainer/devcontainer.json'))
    package = json.loads(read('package.json'))

    node_feature = devcontainer['features']['ghcr.io/devcontainers/features/node:2']

    assert f'FROM node:{NODE_VERSION}-alpine AS frontend-build' in dockerfile
    assert f'FROM node:{NODE_VERSION}-bookworm-slim AS node-runtime' in ci_dockerfile
    assert node_feature['version'] == NODE_VERSION
    assert node_feature['npmVersion'] == NPM_VERSION
    assert package['packageManager'] == f'npm@{NPM_VERSION}'
    assert f'npm@{NPM_VERSION}' in dockerfile
    assert f'npm@{NPM_VERSION}' in ci_dockerfile


def test_pyright_is_reproducibly_pinned() -> None:
    dev_in = read('requirements/dev.in')
    dev_lock = read('requirements/dev.txt')

    assert f'pyright=={PYRIGHT_VERSION}' in dev_in
    assert f'pyright=={PYRIGHT_VERSION}' in dev_lock
    assert 'pyright>=1.1.400,<2' not in dev_in
    assert 'pyright>=1.1.400,<2' not in dev_lock


def test_frontend_dependency_lock_remains_package_manager_owned() -> None:
    package = json.loads(read('package.json'))
    package_lock = json.loads(read('package-lock.json'))

    assert package['devDependencies'] == package_lock['packages']['']['devDependencies']


def test_npm_12_major_upgrade_is_deliberately_deferred() -> None:
    development = read('docs/DEVELOPMENT.md')

    assert 'npm 12.0.2' in development
    assert 'Tailwind 4.3.3' in development
    assert 'Prettier 3.9.8' in development
    assert 'deferred' in development.lower()
    assert 'Node 22.23.2' in development
    assert 'npm 10.9.9' in development
    assert 'normal package-manager workflow' in development
