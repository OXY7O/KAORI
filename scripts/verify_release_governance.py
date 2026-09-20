#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
RELEASE_KEYS = ('KAORI_IMAGE', 'APP_VERSION', 'APP_BUILD_SHA', 'APP_BUILD_DATE')
PERSISTENT_TEMPLATES = (
    'deploy/env/app.env.example',
    'deploy/env/secrets.env.example',
    'deploy/env/deploy.env.example',
)


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise AssertionError(f'Missing release-governance file: {relative}')
    return path.read_text(encoding='utf-8')


def env_value(source: str, key: str) -> str:
    match = re.search(rf'(?m)^{re.escape(key)}=(.*)$', source)
    if not match:
        raise AssertionError(f'Missing {key} release metadata variable')
    return match.group(1).strip()


def reject_active_env_key(source: str, key: str, authority: str) -> None:
    if re.search(rf'(?m)^{re.escape(key)}=', source):
        raise AssertionError(f'{authority} must not actively define deployment-managed {key}')


def verify() -> None:
    version_line = read('VERSION').strip()
    if not SEMVER.fullmatch(version_line):
        raise AssertionError(f'VERSION must contain strict Semantic Versioning, got {version_line!r}')

    changelog = read('CHANGELOG.md')
    governance = read('docs/deployment/RELEASE_GOVERNANCE.md')
    release_lifecycle = read('docs/releases/README.md')
    readme = read('README.md')
    settings_readme = read('app/settings/README.md')
    system_information = read('app/settings/system_information.py')
    system_information_template = read('app/templates/settings/general/partials/_system_information.html')
    default_config = read('app/config/default.py')
    env_example = read('.env.example')
    deprecated_production = read('.env.production.example')
    persistent_sources = {relative: read(relative) for relative in PERSISTENT_TEMPLATES}
    production_compose = read('compose.production.yml')
    server_deploy = read('deploy/server/deploy.sh')
    release_state = read('deploy/server/release-state.sh')
    quality_gate = read('scripts/quality_gate.sh')

    version_example = env_value(env_example, 'APP_VERSION')
    if not SEMVER.fullmatch(version_example):
        raise AssertionError(f'APP_VERSION must be strict Semantic Versioning, got {version_example!r}')
    if version_example != version_line:
        raise AssertionError('Development APP_VERSION must match the canonical VERSION product line')
    if f"'{version_line}'" not in default_config:
        raise AssertionError('Default APP_VERSION must match the canonical VERSION product line')

    readme_badge = f'https://img.shields.io/badge/Version-{version_line.replace("-", "--")}-7C3AED'
    if readme_badge not in readme:
        raise AssertionError('README Version badge must match the canonical VERSION product line')

    for key in ('APP_BUILD_SHA', 'APP_BUILD_DATE'):
        env_value(env_example, key)

    for relative, source in persistent_sources.items():
        for key in RELEASE_KEYS:
            reject_active_env_key(source, key, relative)

    if 'DEPRECATED' not in deprecated_production:
        raise AssertionError('.env.production.example must be a deprecation pointer')
    for marker in (
        'deploy/env/app.env.example',
        'deploy/env/secrets.env.example',
        'deploy/env/deploy.env.example',
        '/var/lib/kaori/deploy-state/release.env',
    ):
        if marker not in deprecated_production:
            raise AssertionError(f'Deprecated production env pointer is missing {marker}')

    for key in RELEASE_KEYS:
        if key not in release_state:
            raise AssertionError(f'release-state.sh must own generated {key}')
    for marker in (
        'KAORI_ACTIVE_RELEASE_ENV_FILE',
        '/var/lib/kaori/deploy-state/release.env',
        'validate_release_identity',
        'load_release_env_file',
    ):
        if marker not in release_state:
            raise AssertionError(f'Release-state authority is missing {marker}')

    for marker in (
        'KAORI_IMAGE: ${KAORI_IMAGE:?',
        'APP_VERSION: ${APP_VERSION:?',
        'APP_BUILD_SHA: ${APP_BUILD_SHA:?',
        'APP_BUILD_DATE: ${APP_BUILD_DATE:?',
    ):
        if marker not in production_compose:
            raise AssertionError(f'Production Compose is missing deployment-managed release identity: {marker}')

    for marker in (
        'usage: deploy.sh IMAGE@sha256:<digest> SOURCE_SHA RELEASE_VERSION',
        'app_version="${release_version#v}"',
        'candidate-release.env',
        'export KAORI_IMAGE="$image"',
        'export APP_VERSION="$app_version"',
        'export APP_BUILD_SHA="$source_sha"',
        'export APP_BUILD_DATE="$image_created"',
        'mv -- "$candidate_release_env" "$active_release_env"',
    ):
        if marker not in server_deploy:
            raise AssertionError(f'Server deployment is missing governed release identity behavior: {marker}')

    if '## [Unreleased]' not in changelog:
        raise AssertionError('CHANGELOG.md is missing required release structure: ## [Unreleased]')
    stable_heading = re.search(
        rf'(?m)^## \[{re.escape(version_line)}\] - (\d{{4}}-\d{{2}}-\d{{2}})$',
        changelog,
    )
    stable_notes_path = ROOT / 'docs/releases' / f'KAORI_{version_line.replace(".", "_")}.md'
    if stable_heading and not stable_notes_path.exists():
        raise AssertionError(
            'A stable changelog heading for VERSION requires matching immutable release notes'
        )
    allowed_sections = {'Added', 'Changed', 'Fixed', 'Security', 'Removed'}
    sections = set(re.findall(r'(?m)^### ([A-Za-z]+)$', changelog))
    if not sections or not sections <= allowed_sections:
        raise AssertionError('CHANGELOG.md contains missing or unsupported change-section headings')

    for token in (
        'Semantic Versioning',
        'APP_VERSION',
        'APP_BUILD_SHA',
        'APP_BUILD_DATE',
        'vX.Y.Z',
        'quality_gate.sh --all',
        'verify_final_release.py --all --runtime',
        'docs/releases/KAORI_X_Y_Z.md',
        'VERSION',
        'product version line',
    ):
        if token not in governance:
            raise AssertionError(f'Release governance is missing contract token: {token}')

    for token in ('VERSION', 'product version line', 'vX.Y.Z-rc.N', 'APP_VERSION', 'immutable digest'):
        if token not in release_lifecycle:
            raise AssertionError(f'Release lifecycle is missing authority token: {token}')

    if 'docs/deployment/RELEASE_GOVERNANCE.md' not in readme or 'CHANGELOG.md' not in readme:
        raise AssertionError('Root README must link release governance and changelog')
    if 'VERSION' not in readme or 'current product version line' not in readme:
        raise AssertionError('Root README must document VERSION as the current product version line')
    if 'CHANGELOG.md' not in settings_readme or 'RELEASE_GOVERNANCE.md' not in settings_readme:
        raise AssertionError('Settings documentation must reference canonical release governance')
    if 'VERSION' not in settings_readme or 'current product version line' not in settings_readme:
        raise AssertionError('Settings documentation must distinguish VERSION from deployed APP_VERSION')

    for token in ('APP_VERSION', 'APP_BUILD_SHA', 'APP_BUILD_DATE'):
        if token not in system_information and token != 'APP_VERSION':
            raise AssertionError(f'System Information builder must retain {token} support')
        if token not in system_information_template:
            raise AssertionError(f'System Information release-governance workspace must mention {token}')

    if 'python scripts/verify_release_governance.py' not in quality_gate:
        raise AssertionError('quality_gate.sh must execute verify_release_governance.py')

    print('PASS — KAORI Release Governance')


if __name__ == '__main__':
    verify()
