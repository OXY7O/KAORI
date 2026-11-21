import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NODE_VERSION = '22.23.2'
NPM_VERSION = '10.9.9'
PYRIGHT_VERSION = '1.1.414'
PYPDF_VERSION = '6.21.4'
TAILWIND_VERSION = '4.3.4'
POSTCSS_VERSION = '8.5.33'
BROTLI_VERSION = '1.2.1'
DNSPYTHON_VERSION = '2.9.2'
MAKO_VERSION = '1.4.3'
WERKZEUG_VERSION = '3.1.9'
URLLIB3_VERSION = '2.8.0'
OAUTHLIB_VERSION = '4.0.1'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_node_and_npm_toolchain_is_exact_and_aligned() -> None:
    dockerfile = read('Dockerfile')
    ci_dockerfile = read('.github/ci/Dockerfile')
    devcontainer = json.loads(read('.devcontainer/devcontainer.json'))
    devcontainer_lock = json.loads(read('.devcontainer/devcontainer-lock.json'))
    post_create = read('.devcontainer/post-create.sh')
    package = json.loads(read('package.json'))

    node_feature = devcontainer['features']['ghcr.io/devcontainers/features/node:1']

    assert f'FROM node:{NODE_VERSION}-alpine AS frontend-build' in dockerfile
    assert f'FROM node:{NODE_VERSION}-bookworm-slim AS node-runtime' in ci_dockerfile
    assert node_feature['version'] == NODE_VERSION
    assert 'npmVersion' not in node_feature
    assert 'ghcr.io/devcontainers/features/node:1' in devcontainer_lock['features']
    assert 'ghcr.io/devcontainers/features/node:2' not in devcontainer_lock['features']
    # The Node feature owns npm installation; do not race or replace it with
    # an unconditional root-owned global upgrade during postCreate.
    assert 'sudo npm install --global' not in post_create
    assert 'bash .devcontainer/ensure-frontend.sh' in post_create
    frontend_bootstrap = read('.devcontainer/ensure-frontend.sh')
    assert 'npm ci --no-audit --no-fund' in frontend_bootstrap
    assert 'npm run prepare-frontend' in frontend_bootstrap
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


def test_development_pdf_security_dependency_is_reproducibly_pinned() -> None:
    dev_in = read('requirements/dev.in')
    dev_lock = read('requirements/dev.txt')

    assert f'pypdf=={PYPDF_VERSION}' in dev_in
    assert f'pypdf=={PYPDF_VERSION}' in dev_lock
    assert 'pypdf==6.19.0' not in dev_in
    assert 'pypdf==6.19.0' not in dev_lock


def test_runtime_security_dependency_floor_is_reproducibly_pinned() -> None:
    base_in = read('requirements/base.in')
    base_lock = read('requirements/base.txt')

    assert f'urllib3=={URLLIB3_VERSION}' in base_in
    assert f'urllib3=={URLLIB3_VERSION}' in base_lock
    assert 'urllib3==2.7.0' not in base_in
    assert 'urllib3==2.7.0' not in base_lock

    assert f'oauthlib=={OAUTHLIB_VERSION}' in base_in
    assert f'oauthlib=={OAUTHLIB_VERSION}' in base_lock
    assert 'oauthlib==3.3.1' not in base_in
    assert 'oauthlib==3.3.1' not in base_lock
    assert 'oauthlib==4.0.0' not in base_in
    assert 'oauthlib==4.0.0' not in base_lock

    for name, version, vulnerable in (
        ('Brotli', BROTLI_VERSION, '1.2.0'),
        ('dnspython', DNSPYTHON_VERSION, '2.8.0'),
        ('Mako', MAKO_VERSION, '1.3.12'),
        ('Werkzeug', WERKZEUG_VERSION, '3.1.8'),
    ):
        assert f'{name}=={version}' in base_in
        assert f'{name}=={version}' in base_lock
        assert f'{name}=={vulnerable}' not in base_in
        assert f'{name}=={vulnerable}' not in base_lock

    # Also guard the subsequently disclosed WKS parser advisory floor.
    assert 'dnspython==2.9.0' not in base_in
    assert 'dnspython==2.9.0' not in base_lock


def test_frontend_dependency_lock_remains_package_manager_owned() -> None:
    package = json.loads(read('package.json'))
    package_lock = json.loads(read('package-lock.json'))

    assert package['devDependencies'] == package_lock['packages']['']['devDependencies']


def test_tailwind_postcss_build_prunes_vulnerable_watcher_dependency_chain() -> None:
    package = json.loads(read('package.json'))
    package_lock = json.loads(read('package-lock.json'))
    packages = package_lock['packages']
    direct = package['devDependencies']
    plugin = packages['node_modules/@tailwindcss/postcss']

    assert direct['@tailwindcss/postcss'] == TAILWIND_VERSION
    assert direct['tailwindcss'] == TAILWIND_VERSION
    assert direct['postcss'] == POSTCSS_VERSION
    assert plugin['version'] == TAILWIND_VERSION
    assert plugin['dependencies']['tailwindcss'] == TAILWIND_VERSION
    assert plugin['dependencies']['@tailwindcss/node'] == TAILWIND_VERSION
    assert plugin['dependencies']['@tailwindcss/oxide'] == TAILWIND_VERSION
    assert packages['node_modules/postcss']['version'] == POSTCSS_VERSION

    # CVE-2026-112366: remove the dependency path, not the audit finding.
    retired = {'@tailwindcss/cli', '@parcel/watcher', 'picomatch', 'micromatch', 'braces'}
    assert retired.isdisjoint(direct)
    assert '@parcel/watcher' not in package.get('overrides', {})
    for path in packages:
        name = path.rsplit('node_modules/', 1)[-1]
        assert name not in retired
        assert not name.startswith('@parcel/watcher-')


def test_npm_12_major_upgrade_is_deliberately_deferred() -> None:
    development = read('docs/DEVELOPMENT.md')

    assert 'npm 12.0.2' in development
    assert 'Tailwind 4.3.4' in development
    assert 'Prettier 3.9.10' in development
    assert 'deferred' in development.lower()
    assert 'Node 22.23.2' in development
    assert 'npm 10.9.9' in development
    assert 'normal package-manager workflow' in development
