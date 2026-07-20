from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

TRUE_VALUES = {'1', 'true', 'yes', 'y', 'on'}
PLACEHOLDER_FRAGMENTS = {
    'change-me',
    'replace-me',
    'your-organization',
    'example.com',
}


def _value(name: str) -> str:
    return (os.getenv(name) or '').strip()


def _is_true(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def _contains_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(fragment in lowered for fragment in PLACEHOLDER_FRAGMENTS)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if _value('APP_ENV') != 'production':
        errors.append('APP_ENV must be production.')

    image = _value('KAORI_IMAGE')
    if not image:
        errors.append('KAORI_IMAGE is required.')
    elif _contains_placeholder(image):
        errors.append('KAORI_IMAGE still contains an example placeholder.')
    elif image.endswith(':latest') or ':' not in image.rsplit('/', 1)[-1]:
        warnings.append('Use an immutable version or commit-SHA image tag, not an untagged/latest image.')

    secret_key = _value('SECRET_KEY')
    if len(secret_key) < 32:
        errors.append('SECRET_KEY must contain at least 32 characters; 64+ is recommended.')
    elif _contains_placeholder(secret_key):
        errors.append('SECRET_KEY still contains a placeholder value.')

    database_url = _value('DATABASE_URL')
    if not database_url:
        errors.append('DATABASE_URL is required.')
    elif urlparse(database_url).scheme not in {'postgresql', 'postgres'}:
        errors.append('DATABASE_URL must use a PostgreSQL URL.')
    elif _contains_placeholder(database_url):
        errors.append('DATABASE_URL still contains a placeholder value.')

    trusted_hosts = [value.strip() for value in _value('TRUSTED_HOSTS').split(',') if value.strip()]
    if not trusted_hosts:
        errors.append('TRUSTED_HOSTS must contain at least one production hostname.')
    elif any('://' in value or '/' in value for value in trusted_hosts):
        errors.append('TRUSTED_HOSTS entries must be hostnames only, without scheme or path.')
    elif any(_contains_placeholder(value) for value in trusted_hosts):
        errors.append('TRUSTED_HOSTS still contains an example placeholder.')

    if _is_true('RATELIMIT_ENABLED', True):
        storage_uri = _value('RATELIMIT_STORAGE_URI')
        if not storage_uri:
            errors.append('RATELIMIT_STORAGE_URI is required when rate limiting is enabled.')
        elif storage_uri.startswith('memory://'):
            errors.append('RATELIMIT_STORAGE_URI must not use memory:// in production.')

    redis_url = _value('REDIS_URL')
    if not redis_url:
        errors.append('REDIS_URL is required for production readiness and shared state.')

    celery_broker_url = _value('CELERY_BROKER_URL')
    celery_result_backend = _value('CELERY_RESULT_BACKEND')

    for name, value in (
        ('CELERY_BROKER_URL', celery_broker_url),
        ('CELERY_RESULT_BACKEND', celery_result_backend),
    ):
        if not value:
            errors.append(f'{name} is required for background cluster synchronization.')
        elif urlparse(value).scheme not in {'redis', 'rediss'}:
            errors.append(f'{name} must use a Redis URL.')
        elif _contains_placeholder(value):
            errors.append(f'{name} still contains a placeholder value.')

    if celery_broker_url and celery_result_backend and celery_broker_url == celery_result_backend:
        warnings.append('Use separate Redis logical databases for Celery broker and task results.')

    for name, minimum in (
        ('CELERY_RESULT_EXPIRES_SECONDS', 300),
        ('CELERY_VISIBILITY_TIMEOUT_SECONDS', 300),
        ('CLUSTER_SYNC_LOCK_TTL_SECONDS', 300),
        ('CLUSTER_SYNC_COMPLETED_TTL_SECONDS', 30),
        ('CELERY_WORKER_CONCURRENCY', 1),
        ('INTEGRATION_VALIDATION_LOCK_TTL_SECONDS', 300),
        ('INTEGRATION_VALIDATION_WORKER_CONCURRENCY', 1),
        ('INTEGRATION_RUNTIME_WORKER_CONCURRENCY', 1),
        ('ANALYTICS_WORKER_CONCURRENCY', 1),
        ('FORECASTING_WORKER_CONCURRENCY', 1),
        ('JOB_MAX_ACTIVE_PER_USER', 1),
        ('JOB_MAX_HEAVY_PER_USER', 1),
        ('JOB_MAX_ACTIVE_PER_RESOURCE', 1),
        ('JOB_QUEUED_STALE_SECONDS', 300),
        ('JOB_RUNNING_STALE_SECONDS', 300),
        ('ANALYTICS_QUERY_MAXIMUM_RANGE_DAYS', 1),
        ('ANALYTICS_QUERY_CHUNK_DAYS', 1),
        ('ANALYTICS_QUERY_MINIMUM_STEP_SECONDS', 1),
        ('ANALYTICS_QUERY_MAXIMUM_SAMPLES_PER_SERIES', 1),
        ('ANALYTICS_QUERY_MAX_CONCURRENT_PER_SOURCE', 1),
    ):
        raw = _value(name)
        try:
            if not raw or int(raw) < minimum:
                raise ValueError
        except ValueError:
            errors.append(f'{name} must be an integer greater than or equal to {minimum}.')

    for queue_name, purpose in (
        ('INTEGRATION_VALIDATION_CELERY_QUEUE', 'capability validation'),
        ('INTEGRATION_RUNTIME_CELERY_QUEUE', 'runtime health'),
        ('ANALYTICS_CELERY_QUEUE', 'analytics batch'),
        ('FORECASTING_CELERY_QUEUE', 'forecasting'),
        ('JOB_MAINTENANCE_CELERY_QUEUE', 'job maintenance'),
    ):
        queue_value = _value(queue_name)
        if not queue_value:
            errors.append(f'{queue_name} is required for {purpose} jobs.')
        elif any(character.isspace() for character in queue_value):
            errors.append(f'{queue_name} must not contain whitespace.')

    storage_backend = _value('PROD_REPORT_STORAGE_BACKEND').lower() or 'local'
    if storage_backend not in {'local', 's3'}:
        errors.append('PROD_REPORT_STORAGE_BACKEND must be local or s3.')
    elif storage_backend == 's3' and not _value('PROD_REPORT_S3_BUCKET'):
        errors.append('PROD_REPORT_S3_BUCKET is required when S3 storage is selected.')
    elif storage_backend == 'local':
        warnings.append('Local report storage is suitable only for a controlled single-host deployment.')

    if _is_true('PROXY_FIX_ENABLED', True):
        for name in (
            'PROXY_FIX_X_FOR',
            'PROXY_FIX_X_PROTO',
            'PROXY_FIX_X_HOST',
            'PROXY_FIX_X_PORT',
            'PROXY_FIX_X_PREFIX',
        ):
            raw = _value(name)
            try:
                if raw and int(raw) < 0:
                    raise ValueError
            except ValueError:
                errors.append(f'{name} must be a non-negative integer.')

    if _value('ADMIN_PASSWORD'):
        warnings.append('Remove ADMIN_PASSWORD after the first bootstrap-admin operation.')

    for warning in warnings:
        print(f'WARNING: {warning}')

    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        print(f'Production environment validation failed with {len(errors)} error(s).', file=sys.stderr)
        return 1

    print('Production environment validation passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
