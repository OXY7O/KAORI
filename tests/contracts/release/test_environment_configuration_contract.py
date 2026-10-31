from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
APP_ENV = 'deploy/env/app.env.example'
SECRETS_ENV = 'deploy/env/secrets.env.example'
DEPLOY_ENV = 'deploy/env/deploy.env.example'
RC_ENV = 'example/kaori/.env.example'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_environment_templates_cover_current_operational_contract() -> None:
    for relative in ('.env.example', APP_ENV):
        source = read(relative)
        for token in (
            'KAORI_PUBLIC_BASE_URL=',
            'TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS=30',
            'TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS=7',
            'INTEGRATION_RUNTIME_MONITORING_ENABLED=true',
            'INTEGRATION_RUNTIME_MONITORING_INTERVAL_MINUTES=5',
            'INTEGRATION_RUNTIME_MAX_TASKS_PER_CHILD=500',
            'INTEGRATION_VALIDATION_MAX_TASKS_PER_CHILD=100',
            'ALERT_INTELLIGENCE_NOTIFICATION_ENABLED=true',
            'ALERT_INTELLIGENCE_NOTIFICATION_INTERVAL_MINUTES=1',
            'NOTIFICATION_DELIVERY_TIMEOUT_SECONDS=10',
            'NOTIFICATION_DELIVERY_MAX_ATTEMPTS=3',
            'SOURCE_CONTROL_WEBHOOK_INGRESS_ENABLED=false',
            'SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED=false',
        ):
            assert token in source


def test_production_environment_keeps_release_identity_deployment_managed() -> None:
    persistent = '\n'.join(read(relative) for relative in (APP_ENV, SECRETS_ENV, DEPLOY_ENV))
    normalized = f'\n{persistent}'

    for variable in ('KAORI_IMAGE', 'APP_VERSION', 'APP_BUILD_SHA', 'APP_BUILD_DATE'):
        assert f'\n{variable}=' not in normalized

    deprecated = read('.env.production.example')
    assert 'DEPRECATED' in deprecated
    assert 'deploy/env/app.env.example' in deprecated
    assert 'deploy/env/secrets.env.example' in deprecated
    assert 'deploy/env/deploy.env.example' in deprecated
    assert '/var/lib/kaori/deploy-state/release.env' in deprecated


def test_environment_contract_uses_canonical_storage_and_public_url_names() -> None:
    sources = '\n'.join(
        (
            read('.env.example'),
            read(APP_ENV),
            read(SECRETS_ENV),
            read(DEPLOY_ENV),
            read('app/config/default.py'),
            read('app/config/development.py'),
            read('app/config/production.py'),
            read('scripts/validate_production_env.py'),
        )
    )
    for legacy in (
        'DEV_REPORT_',
        'DEV_ARCHIVE_',
        'PROD_REPORT_',
        'PROD_ARCHIVE_',
        'REPORT_PUBLIC_BASE_URL',
    ):
        assert legacy not in sources

    production = read(APP_ENV)
    assert 'REPORT_STORAGE_BACKEND=s3' in production
    assert 'REPORT_S3_BUCKET=kaori-production' in production
    assert 'KAORI_PUBLIC_BASE_URL=https://change-me.example.com' in production


def test_split_environment_contract_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_environment_contract.py'],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f'{result.stdout}\n{result.stderr}'
    assert 'PASS — KAORI Environment Contract' in result.stdout


def test_vault_alert_hmac_secret_has_worker_only_environment_authority() -> None:
    contract = runpy.run_path(str(ROOT / 'scripts/verify_environment_contract.py'))
    key = 'KAORI_VAULT_ALERT_CORRELATION_HMAC_KEY_HEX'
    worker = 'app/intelligence/alert_signals/vault_jobs.py'
    document = 'app/secrets_pki/TELEMETRY_BINDING.md'
    assert contract['WORKER_ONLY_SECRET_AUTHORITIES'] == {key: (worker, document)}
    assert key in contract['accessed_env_keys'](worker)
    assert key in read(document)
    for template in ('.env.example', APP_ENV, SECRETS_ENV, DEPLOY_ENV, RC_ENV):
        assert key not in contract['documented_env_keys'](template), template
    assert contract['verify_worker_only_secrets'](
        runtime_sources=(worker,),
        shared_documented_keys=set(),
    ) == {key}


def test_vault_alert_hmac_secret_rejects_shared_or_foreign_runtime_readers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = runpy.run_path(str(ROOT / 'scripts/verify_environment_contract.py'))
    key = 'KAORI_VAULT_ALERT_CORRELATION_HMAC_KEY_HEX'
    worker = 'app/intelligence/alert_signals/vault_jobs.py'
    validator = contract['verify_worker_only_secrets']
    with pytest.raises(AssertionError, match='shared environment templates'):
        validator(runtime_sources=(worker,), shared_documented_keys={key})

    rogue = 'app/config/default.py'
    monkeypatch.setitem(
        validator.__globals__,
        'accessed_env_keys',
        lambda path: {key} if path in {worker, rogue} else set(),
    )
    with pytest.raises(AssertionError, match='only .* may read this worker-only secret'):
        validator(runtime_sources=(worker, rogue), shared_documented_keys=set())


def test_devcontainer_tailwind_watcher_starts_only_after_frontend_bootstrap() -> None:
    import json

    tasks = json.loads(read('.vscode/tasks.json'))['tasks']
    watchers = [task for task in tasks if task.get('label') == 'KAORI: Watch Tailwind CSS']
    assert len(watchers) == 1

    watcher = watchers[0]
    assert watcher['command'] == 'npm run watch-css'
    assert watcher['isBackground'] is True
    assert watcher['runOptions']['instanceLimit'] == 1
    # A folderOpen watcher races npm ci when the named node_modules volume is fresh.
    assert 'runOn' not in watcher['runOptions']
    assert 'does **not** run automatically on folder open' in read('docs/RUNNING.md')


def test_environment_contract_verifier_is_a_release_gate() -> None:
    assert 'python scripts/verify_environment_contract.py' in read('scripts/quality_gate.sh')
    assert "('Environment Contract', (PYTHON, 'scripts/verify_environment_contract.py'))" in read(
        'scripts/verify_final_release.py'
    )


def test_rc_example_keeps_only_required_operator_overrides() -> None:
    source = read(RC_ENV)

    for token in (
        'KAORI_IMAGE=',
        'APP_VERSION=',
        'APP_BUILD_SHA=',
        'APP_BUILD_DATE=',
        'KAORI_PORT=',
        'SECRET_KEY=',
        'INTEGRATION_CREDENTIAL_KEY=',
        'POSTGRES_PASSWORD=',
        'REDIS_PASSWORD=',
        'ADMIN_USERNAME=',
        'ADMIN_EMAIL=',
        'ADMIN_PASSWORD=',
        'KAORI_PUBLIC_BASE_URL=',
        'TRUSTED_HOSTS=',
        'PROXY_FIX_ENABLED=false',
    ):
        assert token in source

    for inherited_default in (
        'RATELIMIT_ENABLED=',
        'AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME=',
        'KUBERNETES_SECRET_REVEAL_ENABLED=',
        'REPORT_STORAGE_BACKEND=',
        'REPORT_LOCAL_STORAGE_DIR=',
        'REPORT_RENDER_STAGING_DIR=',
        'REPORT_DOWNLOAD_CACHE_DIR=',
        'ARCHIVE_DOWNLOAD_CACHE_DIR=',
        'ARCHIVE_STAGING_DIR=',
        'REPORT_SCHEDULE_TIMEZONE=',
        'AUTOMATION_EXECUTION_ENABLED=',
        'CUSTOM_RUNBOOK_AUTHORING_ENABLED=',
    ):
        assert inherited_default not in source


def test_environment_documentation_explains_split_and_minimal_rc_authorities() -> None:
    documentation = read('docs/deployment/ENVIRONMENT_CONFIGURATION.md').lower()

    for authority in (APP_ENV, SECRETS_ENV, DEPLOY_ENV, RC_ENV):
        assert authority.lower() in documentation

    assert 'intentionally minimal' in documentation
    assert 'safe application defaults' in documentation
    assert '.env.production.example' in documentation
    assert 'deprecated and inactive' in documentation


def test_testing_environment_overrides_remain_test_harness_only() -> None:
    testing = read('app/config/testing.py')
    persistent = '\n'.join(read(relative) for relative in ('.env.example', RC_ENV, APP_ENV, SECRETS_ENV, DEPLOY_ENV))

    for token in (
        'TEST_DATABASE_URL',
        'TEST_SECRET_KEY',
        'TEST_REPORT_STORAGE_BACKEND',
        'TEST_REPORT_LOCAL_STORAGE_DIR',
        'TEST_REPORT_RENDER_STAGING_DIR',
        'TEST_REPORT_DOWNLOAD_CACHE_DIR',
        'TEST_ARCHIVE_LOCAL_STORAGE_DIR',
        'TEST_ARCHIVE_DOWNLOAD_CACHE_DIR',
        'TEST_ARCHIVE_STAGING_DIR',
    ):
        assert token in testing
        assert f'{token}=' not in persistent
