"""Compiled Tailwind CSS ownership and reproducible runtime package contracts (#4355)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CSS_PATH = 'app/static/css/output.css'


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_compiled_css_is_gitignored_and_generated_from_canonical_source() -> None:
    gitignore = _read('.gitignore').splitlines()
    dockerignore = _read('.dockerignore').splitlines()
    package = json.loads(_read('package.json'))
    verifier = _read('scripts/verify_css_build.mjs')

    assert f'/{CSS_PATH}' in gitignore
    assert f'/{CSS_PATH}' in dockerignore
    assert 'frontend/styles.css' in package['scripts']['build-css']
    assert f'-o ./{CSS_PATH} --minify' in package['scripts']['build-css']
    assert 'node ./scripts/verify_css_build.mjs' in package['scripts']['build-css']
    assert CSS_PATH in verifier
    assert '--kaori-brand-primary' in verifier
    assert '.bg-surface-card' in verifier


def test_runtime_zip_builds_and_checks_compiled_css_before_packaging() -> None:
    archive = _read('scripts/build_runtime_archive.sh')
    install = 'npm ci --no-audit --no-fund'
    build = 'npm run build-frontend'
    verify = 'npm run verify-frontend'
    copy = 'copy_tree app'

    assert archive.index(install) < archive.index(build) < archive.index(verify) < archive.index(copy)
    assert '[[ -s app/static/css/output.css ]]' in archive
    assert "'kaori/app/static/css/output.css'" in archive
    assert "'kaori/app/static/vendor/manifest.json'" in archive
    assert "'kaori/app/static/fonts/inter/inter-latin-wght-normal.woff2'" in archive
    assert 'missing required frontend assets' in archive


def test_bootstrap_and_docs_exclude_css_from_commit_instructions() -> None:
    bootstrap = _read('scripts/bootstrap_frontend_assets.sh')
    docs = _read('docs/DEVELOPMENT.md') + _read('docs/RUNNING.md')
    source_archive = _read('scripts/build_source_archive.sh')

    assert 'npm run prepare-frontend' in bootstrap
    assert 'app/static/css/output.css is generated and ignored' in bootstrap
    assert 'Commit app/static/vendor, app/static/css/output.css' not in bootstrap
    assert 'Do not commit the compiled file' in docs
    assert 'git archive' in source_archive


def test_production_image_uses_an_independent_frontend_build() -> None:
    dockerfile = _read('Dockerfile')
    package = json.loads(_read('package.json'))

    frontend = dockerfile.split('FROM node:22.23.2-alpine AS frontend-build', 1)[1].split('FROM base AS production', 1)[
        0
    ]
    production = dockerfile.split('FROM base AS production', 1)[1]
    assert 'npm ci' in frontend
    assert 'npm run build-frontend' in frontend
    assert 'npm run verify-frontend' in frontend
    assert 'COPY --from=frontend-build --chown=kaori:kaori' in production
    assert '/build/app/static/css/output.css' in production
    assert 'build-css' in package['scripts']


def test_static_gate_builds_generated_css_before_dark_mode_verification() -> None:
    gate = _read('scripts/quality_gate.sh')
    static = gate.split('run_static() {', 1)[1].split('run_tests() {', 1)[0]
    install = "run_timed_setup 'Static CSS npm dependencies' npm ci --no-audit --no-fund"
    build = "run_timed_setup 'Static CSS build' npm run build-css"
    dark = "'Dark Mode Standard' 'python scripts/verify_dark_mode_standard.py'"

    assert static.index(install) < static.index(build) < static.index(dark)
    assert 'run_timed_setup' in gate
    verifier = _read('scripts/verify_dark_mode_standard.py')
    assert 'compiled = _read(COMPILED)' in verifier
    assert "'compiled CSS'" in verifier
