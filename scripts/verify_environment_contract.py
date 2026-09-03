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

APP_TEMPLATE = 'deploy/env/app.env.example'
SECRETS_TEMPLATE = 'deploy/env/secrets.env.example'
DEPLOY_TEMPLATE = 'deploy/env/deploy.env.example'
DEPRECATED_PRODUCTION_TEMPLATE = '.env.production.example'
PERSISTENT_PRODUCTION_TEMPLATES = (APP_TEMPLATE, SECRETS_TEMPLATE, DEPLOY_TEMPLATE)
RELEASE_KEYS = {'KAORI_IMAGE', 'APP_VERSION', 'APP_BUILD_SHA', 'APP_BUILD_DATE'}
COMPOSE_COMPAT_KEYS = {'KAORI_ENV_FILE', 'KAORI_BIND_ADDRESS', 'KAORI_PORT'}

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

SENSITIVE_KEYS = {
    'SECRET_KEY',
    'INTEGRATION_CREDENTIAL_KEY',
    'INTEGRATION_CREDENTIAL_PREVIOUS_KEYS',
    'POSTGRES_PASSWORD',
    'REDIS_PASSWORD',
    'DATABASE_URL',
    'REDIS_URL',
    'CELERY_BROKER_URL',
    'CELERY_RESULT_BACKEND',
    'RATELIMIT_STORAGE_URI',
    'REPORT_S3_ACCESS_KEY_ID',
    'REPORT_S3_SECRET_ACCESS_KEY',
    'ADMIN_PASSWORD',
    'KAORI_LDAP_BIND_PASSWORD',
    'KAORI_GOOGLE_CLIENT_SECRET',
    'KAORI_GITHUB_CLIENT_SECRET',
    'RESOLVER_TOKEN_SIGNING_KEY',
}

DEPLOYMENT_KEYS = {
    'KAORI_APP_ENV_FILE',
    'KAORI_SECRETS_ENV_FILE',
    'KAORI_ACTIVE_RELEASE_ENV_FILE',
    'POSTGRES_DB',
    'POSTGRES_USER',
    'KAORI_POSTGRES_IMAGE',
    'KAORI_REDIS_IMAGE',
    'KAORI_NGINX_IMAGE',
    'KAORI_CERTBOT_IMAGE',
    'KAORI_PUBLIC_DOMAIN',
    'KAORI_PUBLIC_IP',
    'KAORI_LETSENCRYPT_EMAIL',
    'KAORI_NGINX_RELOAD_INTERVAL_SECONDS',
    'KAORI_CERTBOT_RENEW_INTERVAL_SECONDS',
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


def verify() -> None:
    default_keys = accessed_env_keys('app/config/default.py')
    notification_keys = accessed_env_keys('app/integrations/delivery/notification_channels/config.py')
    common_keys = default_keys | notification_keys | COMMON_EXTRA_KEYS
    development_compose_keys = compose_env_keys('compose.yml', '.devcontainer/compose.devcontainer.yml')
    production_config_keys = accessed_env_keys('app/config/production.py', 'gunicorn.conf.py')

    assert_no_duplicates('.env.example')
    for relative in PERSISTENT_PRODUCTION_TEMPLATES:
        assert_no_duplicates(relative)

    development_keys = documented_env_keys('.env.example')
    missing_development = sorted((common_keys | development_compose_keys) - development_keys)
    if missing_development:
        raise AssertionError('.env.example is missing environment contract keys: ' + ', '.join(missing_development))

    persistent_sets = {relative: documented_env_keys(relative) for relative in PERSISTENT_PRODUCTION_TEMPLATES}
    persistent_union = set().union(*persistent_sets.values())
    required_runtime = common_keys | production_config_keys
    missing_runtime = sorted(required_runtime - persistent_union)
    if missing_runtime:
        raise AssertionError('Split production environment is missing runtime keys: ' + ', '.join(missing_runtime))

    ownership: dict[str, list[str]] = {}
    for relative, keys in persistent_sets.items():
        for key in keys:
            ownership.setdefault(key, []).append(relative)
    overlaps = {key: paths for key, paths in ownership.items() if len(paths) > 1}
    if overlaps:
        details = '; '.join(f'{key}: {", ".join(paths)}' for key, paths in sorted(overlaps.items()))
        raise AssertionError('Persistent production environment keys must have one authority: ' + details)

    app_keys = persistent_sets[APP_TEMPLATE]
    secret_keys = persistent_sets[SECRETS_TEMPLATE]
    deploy_keys = persistent_sets[DEPLOY_TEMPLATE]
    missing_sensitive = sorted(SENSITIVE_KEYS - secret_keys)
    if missing_sensitive:
        raise AssertionError('secrets.env.example is missing sensitive keys: ' + ', '.join(missing_sensitive))
    leaked_sensitive = sorted(SENSITIVE_KEYS & (app_keys | deploy_keys))
    if leaked_sensitive:
        raise AssertionError('Sensitive keys leaked outside secrets.env.example: ' + ', '.join(leaked_sensitive))
    missing_deployment = sorted(DEPLOYMENT_KEYS - deploy_keys)
    if missing_deployment:
        raise AssertionError('deploy.env.example is missing adapter keys: ' + ', '.join(missing_deployment))

    for key in RELEASE_KEYS:
        if key in persistent_union:
            raise AssertionError(f'Persistent production environment must not define release-managed {key}')

    production_compose_keys = compose_env_keys('compose.production.yml', 'deploy/vps/compose.vps.yml')
    undocumented_compose = sorted(
        production_compose_keys - persistent_union - RELEASE_KEYS - COMPOSE_COMPAT_KEYS
    )
    if undocumented_compose:
        raise AssertionError('Compose references undocumented production keys: ' + ', '.join(undocumented_compose))

    deprecated = read(DEPRECATED_PRODUCTION_TEMPLATE)
    if 'DEPRECATED' not in deprecated or 'deploy/env/app.env.example' not in deprecated:
        raise AssertionError('.env.production.example must point operators to the split environment contract')
    if active_env_keys(DEPRECATED_PRODUCTION_TEMPLATE):
        raise AssertionError('.env.production.example must not remain an active production authority')

    source_contract = '\n'.join(
        (
            read('.env.example'),
            *(read(relative) for relative in PERSISTENT_PRODUCTION_TEMPLATES),
            read('app/config/default.py'),
            read('app/config/development.py'),
            read('app/config/production.py'),
            read('scripts/validate_production_env.py'),
        )
    )
    forbidden_hits = sorted(token for token in FORBIDDEN_ENV_TOKENS if token in source_contract)
    if forbidden_hits:
        raise AssertionError('Legacy/obsolete environment variables remain: ' + ', '.join(forbidden_hits))

    operational = read(APP_TEMPLATE)
    for token in (
        'KAORI_PUBLIC_BASE_URL=',
        'TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS=',
        'TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS=',
        'INTEGRATION_RUNTIME_MONITORING_ENABLED=',
        'INTEGRATION_RUNTIME_MONITORING_INTERVAL_MINUTES=',
        'ALERT_SIGNAL_EVALUATION_ENABLED=',
        'ALERT_SIGNAL_EVALUATION_INTERVAL_MINUTES=',
        'ALERT_INTELLIGENCE_NOTIFICATION_ENABLED=',
        'NOTIFICATION_DELIVERY_TIMEOUT_SECONDS=',
        'JOB_MAINTENANCE_WORKER_CPU_LIMIT=',
        'JOB_MAINTENANCE_WORKER_MEMORY_LIMIT=',
    ):
        if token not in operational:
            raise AssertionError(f'{APP_TEMPLATE} is missing required operational setting {token[:-1]}')

    print(
        'PASS — KAORI Environment Contract · '
        f'{len(development_keys)} development keys / '
        f'{len(app_keys)} app + {len(secret_keys)} secret + {len(deploy_keys)} deploy keys'
    )


if __name__ == '__main__':
    verify()
