from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_environment_templates_cover_current_operational_contract() -> None:
    for relative in ('.env.example', '.env.production.example'):
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
        ):
            assert token in source


def test_production_environment_keeps_release_identity_deployment_managed() -> None:
    production = read('.env.production.example')
    normalized = f'\n{production}'

    for variable in (
        'KAORI_IMAGE',
        'APP_VERSION',
        'APP_BUILD_SHA',
        'APP_BUILD_DATE',
    ):
        assert f'\n{variable}=' not in normalized

    assert 'governed deployment' in production.lower()
    assert 'ordinary release' in production.lower()


def test_environment_contract_uses_canonical_storage_and_public_url_names() -> None:
    sources = '\n'.join(
        (
            read('.env.example'),
            read('.env.production.example'),
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

    production = read('.env.production.example')
    assert 'REPORT_STORAGE_BACKEND=s3' in production
    assert 'REPORT_S3_BUCKET=kaori-production' in production
    assert '# ARCHIVE_STORAGE_BACKEND=s3' in production
    assert '# ARCHIVE_S3_BUCKET=kaori-production' in production


def test_environment_contract_verifier_is_a_release_gate() -> None:
    assert 'python scripts/verify_environment_contract.py' in read('scripts/quality_gate.sh')
    assert "('Environment Contract', (PYTHON, 'scripts/verify_environment_contract.py'))" in read(
        'scripts/verify_final_release.py'
    )
