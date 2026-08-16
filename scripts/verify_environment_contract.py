#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_ASSIGNMENT = re.compile(r'^\s*#?\s*([A-Z][A-Z0-9_]*)=')
ACTIVE_ENV_ASSIGNMENT = re.compile(r'^([A-Z][A-Z0-9_]*)=')
ENV_ACCESS = re.compile(
    r'(?:os\.getenv|os\.environ\.get|environ\.get|_env_str|_env_int|_env_bool|'
    r"_env_optional_str|_bounded_env_int|_bounded_int|_env_csv)\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]"
)
COMPOSE_ENV = re.compile(r'\$\$?\{([A-Z][A-Z0-9_]*)(?::[-+?][^}]*)?\}')

COMMON_EXTRA_KEYS = {
    'ADMIN_EMAIL',
    'ADMIN_PASSWORD',
    'ADMIN_USERNAME',
    'DB_WAIT_ATTEMPTS',
    'DB_WAIT_INTERVAL_SECONDS',
    'KAORI_GITHUB_CLIENT_SECRET',
    'KAORI_GOOGLE_CLIENT_SECRET',
    'WAIT_FOR_DB',
}

PRODUCTION_ONLY_KEYS = {
    'GUNICORN_GRACEFUL_TIMEOUT',
    'GUNICORN_KEEPALIVE',
    'GUNICORN_LOG_LEVEL',
    'GUNICORN_THREADS',
    'GUNICORN_TIMEOUT',
    'GUNICORN_WORKERS',
    'KAORI_BIND_ADDRESS',
    'KAORI_IMAGE',
    'KAORI_PORT',
    'TRUSTED_HOSTS',
}

FORBIDDEN_ENV_TOKENS = {
    'CELERY_WORKER_CONCURRENCY',
    'DEV_ARCHIVE_LOCAL_STORAGE_DIR',
    'DEV_ARCHIVE_STORAGE_BACKEND',
    'DEV_REPORT_LOCAL_STORAGE_DIR',
    'DEV_REPORT_STORAGE_BACKEND',
    'PROD_ARCHIVE_LOCAL_STORAGE_DIR',
    'PROD_ARCHIVE_S3_ACCESS_KEY_ID',
    'PROD_ARCHIVE_S3_BUCKET',
    'PROD_ARCHIVE_S3_ENDPOINT_URL',
    'PROD_ARCHIVE_S3_FORCE_PATH_STYLE',
    'PROD_ARCHIVE_S3_PREFIX',
    'PROD_ARCHIVE_S3_REGION',
    'PROD_ARCHIVE_S3_SECRET_ACCESS_KEY',
    'PROD_ARCHIVE_STORAGE_BACKEND',
    'PROD_REPORT_LOCAL_STORAGE_DIR',
    'PROD_REPORT_S3_ACCESS_KEY_ID',
    'PROD_REPORT_S3_BUCKET',
    'PROD_REPORT_S3_ENDPOINT_URL',
    'PROD_REPORT_S3_FORCE_PATH_STYLE',
    'PROD_REPORT_S3_PREFIX',
    'PROD_REPORT_S3_REGION',
    'PROD_REPORT_S3_SECRET_ACCESS_KEY',
    'PROD_REPORT_STORAGE_BACKEND',
    'REPORT_PUBLIC_BASE_URL',
    'REPORT_TELEGRAM_BOT_TOKEN',
    'REPORT_TELEGRAM_CHAT_ID',
    'REPORT_DELIVERY_TIMEOUT_SECONDS',
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def documented_env_keys(relative: str) -> set[str]:
    return {match.group(1) for line in read(relative).splitlines() if (match := ENV_ASSIGNMENT.match(line)) is not None}


def active_env_keys(relative: str) -> list[str]:
    return [
        match.group(1)
        for line in read(relative).splitlines()
        if (match := ACTIVE_ENV_ASSIGNMENT.match(line)) is not None
    ]


def accessed_env_keys(*relatives: str) -> set[str]:
    keys: set[str] = set()
    for relative in relatives:
        keys.update(ENV_ACCESS.findall(read(relative)))
    return keys


def compose_env_keys(*relatives: str) -> set[str]:
    keys: set[str] = set()
    for relative in relatives:
        keys.update(COMPOSE_ENV.findall(read(relative)))
    return keys


def assert_no_duplicates(relative: str) -> None:
    keys = active_env_keys(relative)
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise AssertionError(f'{relative} contains duplicate active variables: {", ".join(duplicates)}')


def assert_documented(relative: str, required: set[str]) -> None:
    missing = sorted(required - documented_env_keys(relative))
    if missing:
        raise AssertionError(f'{relative} is missing environment contract keys: {", ".join(missing)}')


def verify() -> None:
    default_keys = accessed_env_keys('app/config/default.py')
    notification_keys = accessed_env_keys('app/notification_channels/config.py')
    common_keys = default_keys | notification_keys | COMMON_EXTRA_KEYS

    development_compose_keys = compose_env_keys(
        'compose.yml',
        '.devcontainer/compose.devcontainer.yml',
    )
    production_compose_keys = compose_env_keys('compose.production.yml')
    production_config_keys = accessed_env_keys('app/config/production.py', 'gunicorn.conf.py')

    assert_no_duplicates('.env.example')
    assert_no_duplicates('.env.production.example')

    assert_documented('.env.example', common_keys | development_compose_keys)
    assert_documented(
        '.env.production.example',
        common_keys | production_compose_keys | production_config_keys | PRODUCTION_ONLY_KEYS,
    )

    source_contract = '\n'.join(
        (
            read('.env.example'),
            read('.env.production.example'),
            read('app/config/default.py'),
            read('app/config/development.py'),
            read('app/config/production.py'),
            read('scripts/validate_production_env.py'),
        )
    )
    forbidden_hits = sorted(token for token in FORBIDDEN_ENV_TOKENS if token in source_contract)
    if forbidden_hits:
        raise AssertionError('Legacy/obsolete environment variables remain: ' + ', '.join(forbidden_hits))

    for relative in ('.env.example', '.env.production.example'):
        source = read(relative)
        for token in (
            'KAORI_PUBLIC_BASE_URL=',
            'TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS=',
            'TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS=',
            'INTEGRATION_RUNTIME_MONITORING_ENABLED=',
            'INTEGRATION_RUNTIME_MONITORING_INTERVAL_MINUTES=',
            'INTEGRATION_RUNTIME_MAX_TASKS_PER_CHILD=',
            'INTEGRATION_VALIDATION_MAX_TASKS_PER_CHILD=',
            'ALERT_INTELLIGENCE_NOTIFICATION_ENABLED=',
            'ALERT_INTELLIGENCE_NOTIFICATION_INTERVAL_MINUTES=',
            'NOTIFICATION_DELIVERY_TIMEOUT_SECONDS=',
            'NOTIFICATION_DELIVERY_MAX_ATTEMPTS=',
        ):
            if token not in source:
                raise AssertionError(f'{relative} is missing required operational setting {token[:-1]}')

    production = read('.env.production.example')
    for token in (
        'JOB_MAINTENANCE_WORKER_CPU_LIMIT=',
        'JOB_MAINTENANCE_WORKER_MEMORY_LIMIT=',
    ):
        if token not in production:
            raise AssertionError(f'.env.production.example is missing deployment resource control {token[:-1]}')

    print(
        'PASS — KAORI Environment Contract · '
        f'{len(documented_env_keys(".env.example"))} development keys / '
        f'{len(documented_env_keys(".env.production.example"))} production keys'
    )


if __name__ == '__main__':
    verify()
