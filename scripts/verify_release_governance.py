#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


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


def verify() -> None:
    changelog = read('CHANGELOG.md')
    governance = read('docs/deployment/RELEASE_GOVERNANCE.md')
    readme = read('README.md')
    settings_readme = read('app/settings/README.md')
    system_information = read('app/settings/system_information.py')
    system_context = read('app/templates/settings/general/partials/_system_information_context.html')
    default_config = read('app/config/default.py')
    env_example = read('.env.example')
    env_production = read('.env.production.example')
    quality_gate = read('scripts/quality_gate.sh')

    version_example = env_value(env_example, 'APP_VERSION')
    version_production = env_value(env_production, 'APP_VERSION')
    if version_example != version_production:
        raise AssertionError('APP_VERSION differs between development and production examples')
    if not SEMVER.fullmatch(version_example):
        raise AssertionError(f'APP_VERSION must be strict Semantic Versioning, got {version_example!r}')
    if f"'{version_example}'" not in default_config:
        raise AssertionError('Default APP_VERSION must match environment examples')

    for source_name, source in (('.env.example', env_example), ('.env.production.example', env_production)):
        for key in ('APP_BUILD_SHA', 'APP_BUILD_DATE'):
            env_value(source, key)

    for token in ('## [Unreleased]', f'## [{version_example}]'):
        if token not in changelog:
            raise AssertionError(f'CHANGELOG.md is missing required release structure: {token}')
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
    ):
        if token not in governance:
            raise AssertionError(f'Release governance is missing contract token: {token}')

    if 'docs/deployment/RELEASE_GOVERNANCE.md' not in readme or 'CHANGELOG.md' not in readme:
        raise AssertionError('Root README must link release governance and changelog')
    if 'CHANGELOG.md' not in settings_readme or 'RELEASE_GOVERNANCE.md' not in settings_readme:
        raise AssertionError('Settings documentation must reference canonical release governance')

    for token in ('APP_VERSION', 'APP_BUILD_SHA', 'APP_BUILD_DATE'):
        if token not in system_information and token != 'APP_VERSION':
            raise AssertionError(f'System Information builder must retain {token} support')
        if token not in system_context:
            raise AssertionError(f'System Information release-governance context must mention {token}')

    if 'python scripts/verify_release_governance.py' not in quality_gate:
        raise AssertionError('quality_gate.sh must execute verify_release_governance.py')

    print(
        f'KAORI release governance passed for current baseline {version_example}; changelog and immutable build metadata contracts are aligned.'
    )


if __name__ == '__main__':
    verify()
