#!/usr/bin/env python3
from __future__ import annotations

import argparse
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



RELEASE_NOTE_SECTIONS = ('Highlights', 'Improvements', 'Fixes', 'Known Limitations')


def verify_reviewed_release_notes(version: str, candidate_tag: str) -> Path:
    """Validate a reviewed, release-specific narrative before any stable publication."""
    if not SEMVER.fullmatch(version):
        raise AssertionError(f'Invalid requested stable SemVer: {version}')
    if not re.fullmatch(rf'v{re.escape(version)}-rc\.[1-9][0-9]*', candidate_tag):
        raise AssertionError('Accepted candidate must match the requested stable version')

    notes_path = ROOT / 'docs' / 'releases' / f'KAORI_{version.replace(".", "_")}.md'
    if not notes_path.is_file():
        raise AssertionError(f'Missing human-reviewed release notes: {notes_path.relative_to(ROOT)}')
    notes = notes_path.read_text(encoding='utf-8')
    if not notes.startswith(f'# KAORI v{version}\n'):
        raise AssertionError('Reviewed release notes must begin with the exact stable version')
    if f'**Accepted release candidate:** `{candidate_tag}`' not in notes:
        raise AssertionError('Reviewed release notes do not identify the accepted release candidate')

    uat = re.search(
        r'(?m)^\*\*Human UAT evidence:\*\* '
        r'https://github\.com/OXY7O/KAORI/issues/[1-9][0-9]*#issuecomment-[1-9][0-9]*
    version_line = read('VERSION').strip()
    if not SEMVER.fullmatch(version_line):
        raise AssertionError(f'VERSION must contain strict Semantic Versioning, got {version_line!r}')

    rc_workflow = read('.github/workflows/publish-staging-image.yml')
    if 'INITIAL_VERSION="$(cat VERSION)"' not in rc_workflow:
        raise AssertionError('RC bootstrap must derive the first-public version from VERSION')
    if "INITIAL_VERSION='0.1.0'" in rc_workflow:
        raise AssertionError('RC bootstrap must not hardcode the obsolete 0.1.0 train')

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
        raise AssertionError('A stable changelog heading for VERSION requires matching immutable release notes')
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
    main()
,
        notes,
    )
    if uat is None:
        raise AssertionError('Reviewed release notes need an explicit issue-comment Human UAT evidence link')

    headings = re.findall(r'(?m)^## ([^\n]+)
    version_line = read('VERSION').strip()
    if not SEMVER.fullmatch(version_line):
        raise AssertionError(f'VERSION must contain strict Semantic Versioning, got {version_line!r}')

    rc_workflow = read('.github/workflows/publish-staging-image.yml')
    if 'INITIAL_VERSION="$(cat VERSION)"' not in rc_workflow:
        raise AssertionError('RC bootstrap must derive the first-public version from VERSION')
    if "INITIAL_VERSION='0.1.0'" in rc_workflow:
        raise AssertionError('RC bootstrap must not hardcode the obsolete 0.1.0 train')

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
        raise AssertionError('A stable changelog heading for VERSION requires matching immutable release notes')
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
, notes)
    if headings != list(RELEASE_NOTE_SECTIONS):
        raise AssertionError('Reviewed release notes require ordered product sections only')
    for heading in RELEASE_NOTE_SECTIONS:
        match = re.search(
            rf'(?ms)^## {re.escape(heading)}\n(.*?)(?=^## |\Z)',
            notes,
        )
        if match is None:
            raise AssertionError(f'Missing reviewed release section: {heading}')
        body = match.group(1).strip()
        if len(body) < 12 or re.search(r'(?i)\b(?:TODO|TBD|PLACEHOLDER)\b|<[^>]+>', body):
            raise AssertionError(f'Release section {heading} is empty or contains placeholders')

    changelog = read('CHANGELOG.md')
    marker = '## [Unreleased]'
    if marker not in changelog:
        raise AssertionError('CHANGELOG.md must retain [Unreleased] until stable is published')
    changes = changelog.split(marker, 1)[1].split('\n## ', 1)[0]
    if not re.search(r'(?m)^- .{10,}
    version_line = read('VERSION').strip()
    if not SEMVER.fullmatch(version_line):
        raise AssertionError(f'VERSION must contain strict Semantic Versioning, got {version_line!r}')

    rc_workflow = read('.github/workflows/publish-staging-image.yml')
    if 'INITIAL_VERSION="$(cat VERSION)"' not in rc_workflow:
        raise AssertionError('RC bootstrap must derive the first-public version from VERSION')
    if "INITIAL_VERSION='0.1.0'" in rc_workflow:
        raise AssertionError('RC bootstrap must not hardcode the obsolete 0.1.0 train')

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
        raise AssertionError('A stable changelog heading for VERSION requires matching immutable release notes')
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
, changes):
        raise AssertionError('CHANGELOG.md [Unreleased] must document material changes')
    return notes_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Verify KAORI release-governance source authority')
    parser.add_argument('--reviewed-notes-version', help='Requested stable SemVer without v prefix')
    parser.add_argument('--candidate-tag', help='Exact accepted vX.Y.Z-rc.N')
    args = parser.parse_args()
    if args.reviewed_notes_version is not None:
        if not args.candidate_tag:
            parser.error('--candidate-tag is required with --reviewed-notes-version')
        notes = verify_reviewed_release_notes(args.reviewed_notes_version, args.candidate_tag)
        print(f'PASS — Reviewed stable release notes: {notes.relative_to(ROOT)}')
        return
    if args.candidate_tag is not None:
        parser.error('--candidate-tag requires --reviewed-notes-version')
    verify()


def verify() -> None:
    version_line = read('VERSION').strip()
    if not SEMVER.fullmatch(version_line):
        raise AssertionError(f'VERSION must contain strict Semantic Versioning, got {version_line!r}')

    rc_workflow = read('.github/workflows/publish-staging-image.yml')
    if 'INITIAL_VERSION="$(cat VERSION)"' not in rc_workflow:
        raise AssertionError('RC bootstrap must derive the first-public version from VERSION')
    if "INITIAL_VERSION='0.1.0'" in rc_workflow:
        raise AssertionError('RC bootstrap must not hardcode the obsolete 0.1.0 train')

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
        raise AssertionError('A stable changelog heading for VERSION requires matching immutable release notes')
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
