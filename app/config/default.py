import os
from pathlib import Path

from celery.schedules import crontab
from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parents[2]


def _load_environment_files() -> None:
    """Load .env and optional .env.<APP_ENV> without overriding real OS env vars.

    Precedence:
    1. OS environment variables
    2. .env.<APP_ENV> values
    3. .env values
    """
    base_env_file = BASE_DIR / '.env'
    base_values = dotenv_values(
        base_env_file,
    )

    app_env = (
        os.getenv(
            'APP_ENV',
        )
        or base_values.get(
            'APP_ENV',
        )
        or 'development'
    )

    environment_env_file = BASE_DIR / f'.env.{app_env}'
    environment_values = dotenv_values(
        environment_env_file,
    )

    merged_values = {
        **base_values,
        **environment_values,
    }

    for key, value in merged_values.items():
        if value is None:
            continue

        os.environ.setdefault(
            key,
            value,
        )


def _env_str(
    name: str,
    default: str = '',
) -> str:
    return os.getenv(
        name,
        default,
    )


def _env_optional_str(
    name: str,
) -> str | None:
    value = os.getenv(
        name,
        '',
    ).strip()

    return value or None


def _env_int(
    name: str,
    default: int = 0,
) -> int:
    value = os.getenv(
        name,
    )

    if value is None:
        return default

    try:
        return int(
            value.strip(),
        )
    except ValueError:
        return default


def _env_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = os.getenv(
        name,
    )

    if value is None:
        return default

    return value.strip().lower() in {
        '1',
        'true',
        'yes',
        'y',
        'on',
    }


def _bounded_env_int(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    return max(minimum, min(_env_int(name, default), maximum))


def _retention_queue_name() -> str:
    return _env_str('RETENTION_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'


def _build_maintenance_beat_schedule() -> dict[str, dict[str, object]]:
    schedule: dict[str, dict[str, object]] = {}
    if _env_bool('ACTIVITY_RETENTION_SCHEDULE_ENABLED', True) or _env_bool('JOB_EXECUTION_RETENTION_ENABLED', True):
        schedule['data-lifecycle-dispatcher'] = {
            'task': 'app.retention.tasks.run_scheduled_retention',
            'schedule': crontab(minute='*/15'),
            'options': {
                'queue': _retention_queue_name(),
            },
        }
    if _env_bool('JOB_POLICY_SCHEDULER_ENABLED', True):
        schedule['job-policy-dispatcher'] = {
            'task': 'app.jobs.tasks.dispatch_scheduled_jobs',
            'schedule': crontab(minute='*'),
            'options': {
                'queue': (
                    _env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'
                ),
            },
        }
    if _env_bool('INTEGRATION_RUNTIME_MONITORING_ENABLED', True):
        schedule['integration-runtime-monitoring'] = {
            'task': 'app.integrations.runtime.tasks.refresh_integration_runtime',
            'schedule': crontab(
                minute=f'*/{_bounded_env_int("INTEGRATION_RUNTIME_MONITORING_INTERVAL_MINUTES", 5, 1, 60)}'
            ),
            'options': {
                'queue': _env_str('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime').strip()
                or 'integration-runtime'
            },
        }
    if _env_bool('JOB_RECOVERY_ENABLED', True):
        schedule['job-execution-recovery'] = {
            'task': 'app.jobs.tasks.reconcile_stale_jobs',
            'schedule': crontab(minute=f'*/{_bounded_env_int("JOB_RECOVERY_INTERVAL_MINUTES", 5, 1, 60)}'),
            'options': {
                'queue': (
                    _env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'
                ),
            },
        }
    if _env_bool('RESOLVER_MAINTENANCE_ENABLED', True):
        schedule['resolver-lease-recovery'] = {
            'task': 'app.resolver.tasks.reconcile_stale_execution_leases',
            'schedule': crontab(minute=f'*/{_bounded_env_int("RESOLVER_MAINTENANCE_INTERVAL_MINUTES", 1, 1, 60)}'),
            'options': {
                'queue': _env_str('RESOLVER_MAINTENANCE_CELERY_QUEUE', 'resolver-maintenance').strip()
                or 'resolver-maintenance'
            },
        }
    return schedule


def _normalize_storage_backend(
    value: str | None,
) -> str:
    backend = (value or 'local').strip().lower()

    if backend not in {
        'local',
        's3',
    }:
        return 'local'

    return backend


def _resolve_path(
    value: str | None,
    default: Path,
) -> str:
    raw_value = (
        value
        or str(
            default,
        )
    ).strip()

    path = Path(
        raw_value,
    )

    if path.is_absolute():
        return str(
            path,
        )

    return str(
        BASE_DIR / path,
    )


_load_environment_files()


class Config:
    APP_ENV = _env_str(
        'APP_ENV',
        'development',
    )

    SECRET_KEY = _env_str(
        'SECRET_KEY',
        'change-me',
    )

    # ProxyFix remains disabled outside the production configuration unless
    # a deployment explicitly opts in. Defining the full contract here keeps
    # application-factory behavior deterministic across every environment.
    PROXY_FIX_ENABLED = _env_bool('PROXY_FIX_ENABLED', False)
    PROXY_FIX_X_FOR = _env_int('PROXY_FIX_X_FOR', 1)
    PROXY_FIX_X_PROTO = _env_int('PROXY_FIX_X_PROTO', 1)
    PROXY_FIX_X_HOST = _env_int('PROXY_FIX_X_HOST', 1)
    PROXY_FIX_X_PORT = _env_int('PROXY_FIX_X_PORT', 1)
    PROXY_FIX_X_PREFIX = _env_int('PROXY_FIX_X_PREFIX', 0)

    INTEGRATION_CREDENTIAL_KEY = _env_optional_str(
        'INTEGRATION_CREDENTIAL_KEY',
    )
    INTEGRATION_CREDENTIAL_PREVIOUS_KEYS = _env_str(
        'INTEGRATION_CREDENTIAL_PREVIOUS_KEYS',
        '',
    )

    SQLALCHEMY_DATABASE_URI = _env_str(
        'DATABASE_URL',
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = _env_optional_str(
        'REDIS_URL',
    )

    CELERY_BROKER_URL = _env_str(
        'CELERY_BROKER_URL',
        REDIS_URL or 'redis://redis:6379/1',
    )

    CELERY_RESULT_BACKEND = _env_str(
        'CELERY_RESULT_BACKEND',
        REDIS_URL or 'redis://redis:6379/3',
    )

    CELERY_RESULT_EXPIRES_SECONDS = _env_int(
        'CELERY_RESULT_EXPIRES_SECONDS',
        86400,
    )

    CELERY_VISIBILITY_TIMEOUT_SECONDS = _env_int(
        'CELERY_VISIBILITY_TIMEOUT_SECONDS',
        10800,
    )

    CLUSTER_SYNC_LOCK_TTL_SECONDS = _env_int(
        'CLUSTER_SYNC_LOCK_TTL_SECONDS',
        10800,
    )

    CLUSTER_SYNC_COMPLETED_TTL_SECONDS = _env_int(
        'CLUSTER_SYNC_COMPLETED_TTL_SECONDS',
        300,
    )

    CELERY_TIMEZONE = _env_str(
        'CELERY_TIMEZONE',
        'UTC',
    )

    RETENTION_CELERY_QUEUE = _retention_queue_name()

    INTEGRATION_VALIDATION_CELERY_QUEUE = (
        _env_str('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation').strip() or 'integration-validation'
    )

    INTEGRATION_VALIDATION_LOCK_TTL_SECONDS = _env_int(
        'INTEGRATION_VALIDATION_LOCK_TTL_SECONDS',
        7200,
    )

    INTEGRATION_RUNTIME_CELERY_QUEUE = (
        _env_str('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime').strip() or 'integration-runtime'
    )
    ANALYTICS_CELERY_QUEUE = _env_str('ANALYTICS_CELERY_QUEUE', 'analytics-batch').strip() or 'analytics-batch'
    FORECASTING_CELERY_QUEUE = _env_str('FORECASTING_CELERY_QUEUE', 'forecasting').strip() or 'forecasting'
    JOB_MAINTENANCE_CELERY_QUEUE = _env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'
    RESOLVER_EXECUTION_CELERY_QUEUE = (
        _env_str('RESOLVER_EXECUTION_CELERY_QUEUE', 'resolver-execution').strip() or 'resolver-execution'
    )
    RESOLVER_MAINTENANCE_CELERY_QUEUE = (
        _env_str('RESOLVER_MAINTENANCE_CELERY_QUEUE', 'resolver-maintenance').strip() or 'resolver-maintenance'
    )
    RESOLVER_MAINTENANCE_ENABLED = _env_bool('RESOLVER_MAINTENANCE_ENABLED', True)
    RESOLVER_MAINTENANCE_INTERVAL_MINUTES = _bounded_env_int(
        'RESOLVER_MAINTENANCE_INTERVAL_MINUTES',
        1,
        1,
        60,
    )
    RESOLVER_ENABLED_ACTIONS = _env_str('RESOLVER_ENABLED_ACTIONS', '')
    RESOLVER_KUBERNETES_ALLOWED_NAMESPACES = _env_str('RESOLVER_KUBERNETES_ALLOWED_NAMESPACES', '')
    RESOLVER_TOKEN_SIGNING_KEY = _env_optional_str('RESOLVER_TOKEN_SIGNING_KEY')
    JOB_MAX_ACTIVE_PER_USER = _env_int('JOB_MAX_ACTIVE_PER_USER', 5)
    JOB_MAX_HEAVY_PER_USER = _env_int('JOB_MAX_HEAVY_PER_USER', 1)
    JOB_MAX_ACTIVE_PER_RESOURCE = _env_int('JOB_MAX_ACTIVE_PER_RESOURCE', 2)
    JOB_QUEUED_STALE_SECONDS = _env_int('JOB_QUEUED_STALE_SECONDS', 1800)
    JOB_RUNNING_STALE_SECONDS = _env_int('JOB_RUNNING_STALE_SECONDS', 7200)

    CELERY = {
        'broker_url': CELERY_BROKER_URL,
        'result_backend': CELERY_RESULT_BACKEND,
        'task_default_queue': 'default',
        'task_track_started': True,
        'task_send_sent_event': True,
        'worker_send_task_events': True,
        'result_extended': True,
        'result_expires': CELERY_RESULT_EXPIRES_SECONDS,
        'broker_connection_retry_on_startup': True,
        'worker_prefetch_multiplier': 1,
        'task_acks_late': True,
        'task_reject_on_worker_lost': True,
        'task_inherit_parent_priority': True,
        'task_serializer': 'json',
        'result_serializer': 'json',
        'accept_content': ['json'],
        'timezone': CELERY_TIMEZONE,
        'enable_utc': True,
        'imports': (
            'app.cluster.tasks',
            'app.retention.tasks',
            'app.integrations.runtime.tasks',
            'app.integrations.validation.tasks',
            'app.jobs.tasks',
            'app.resolver.tasks',
        ),
        'task_routes': {
            'app.cluster.tasks.sync_all_clusters': {
                'queue': 'inventory',
            },
            'app.cluster.tasks.sync_single_cluster': {
                'queue': 'inventory',
            },
            'app.retention.tasks.run_domain_retention': {
                'queue': _retention_queue_name(),
            },
            'app.retention.tasks.run_scheduled_retention': {
                'queue': _retention_queue_name(),
            },
            'app.jobs.tasks.dispatch_scheduled_jobs': {
                'queue': JOB_MAINTENANCE_CELERY_QUEUE,
            },
            'app.integrations.runtime.tasks.refresh_integration_runtime': {
                'queue': INTEGRATION_RUNTIME_CELERY_QUEUE,
            },
            'app.integrations.validation.tasks.validate_integration_instance': {
                'queue': INTEGRATION_VALIDATION_CELERY_QUEUE,
            },
            'app.integrations.validation.tasks.validate_integration_binding': {
                'queue': INTEGRATION_VALIDATION_CELERY_QUEUE,
            },
            'app.integrations.validation.tasks.refresh_integration_runtime_instance': {
                'queue': INTEGRATION_RUNTIME_CELERY_QUEUE,
            },
            'app.jobs.tasks.reconcile_stale_jobs': {
                'queue': JOB_MAINTENANCE_CELERY_QUEUE,
            },
            'app.resolver.tasks.execute_authorized_resolution': {
                'queue': RESOLVER_EXECUTION_CELERY_QUEUE,
            },
            'app.resolver.tasks.reconcile_stale_execution_leases': {
                'queue': RESOLVER_MAINTENANCE_CELERY_QUEUE,
            },
        },
        'visibility_timeout': CELERY_VISIBILITY_TIMEOUT_SECONDS,
        'broker_transport_options': {
            'visibility_timeout': CELERY_VISIBILITY_TIMEOUT_SECONDS,
            'queue_order_strategy': 'priority',
            'priority_steps': list(range(10)),
        },
        'result_backend_transport_options': {
            'global_keyprefix': 'kaori:celery:',
            'visibility_timeout': CELERY_VISIBILITY_TIMEOUT_SECONDS,
        },
        'beat_schedule': _build_maintenance_beat_schedule(),
    }

    WTF_CSRF_ENABLED = True

    # Authentication rate limiting.
    # Default storage is in-memory for local MVP testing. Use Redis later for
    # multi-instance deployments, for example: redis://redis:6379/0.
    RATELIMIT_ENABLED = _env_bool(
        'RATELIMIT_ENABLED',
        True,
    )

    RATELIMIT_STORAGE_URI = _env_str(
        'RATELIMIT_STORAGE_URI',
        'memory://',
    )

    AUTH_LOGIN_RATE_LIMIT = _env_str(
        'AUTH_LOGIN_RATE_LIMIT',
        '5 per minute',
    )

    AUTH_LOGIN_RATE_LIMIT_MESSAGE = _env_str(
        'AUTH_LOGIN_RATE_LIMIT_MESSAGE',
        'Too many login attempts. Please wait a minute and try again.',
    )

    AUTH_SSO_RATE_LIMIT = _env_str(
        'AUTH_SSO_RATE_LIMIT',
        '20 per minute',
    )

    AUTH_SSO_RATE_LIMIT_MESSAGE = _env_str(
        'AUTH_SSO_RATE_LIMIT_MESSAGE',
        'Too many SSO attempts. Please wait a minute and start sign-in again.',
    )

    AUTH_SSO_FLOW_TTL_SECONDS = _bounded_env_int(
        'AUTH_SSO_FLOW_TTL_SECONDS',
        600,
        60,
        1800,
    )

    # Persistent sessions are disabled for local super administrators by default.
    # Enable only after the break-glass operating procedure explicitly permits it.
    AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME = _env_bool(
        'AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME',
        False,
    )

    # Plain LDAP transmits credentials without transport encryption and is disabled by default.
    AUTH_LDAP_ALLOW_PLAINTEXT = _env_bool(
        'AUTH_LDAP_ALLOW_PLAINTEXT',
        False,
    )

    # Protected Kubernetes Secret reveal. This capability is globally disabled
    # until an operator explicitly enables it and configures per-cluster controls.
    KUBERNETES_SECRET_REVEAL_ENABLED = _env_bool(
        'KUBERNETES_SECRET_REVEAL_ENABLED',
        False,
    )

    KUBERNETES_SECRET_REVEAL_RATE_LIMIT = _env_str(
        'KUBERNETES_SECRET_REVEAL_RATE_LIMIT',
        '3 per 5 minutes',
    )

    KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS = _bounded_env_int(
        'KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS',
        300,
        60,
        900,
    )

    KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS = _bounded_env_int(
        'KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS',
        15,
        5,
        60,
    )

    KUBERNETES_SECRET_REVEAL_MAX_BYTES = _bounded_env_int(
        'KUBERNETES_SECRET_REVEAL_MAX_BYTES',
        65536,
        1024,
        262144,
    )

    KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES = _bounded_env_int(
        'KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES',
        10,
        1,
        60,
    )

    KUBERNETES_SECRET_REVEAL_PENDING_TTL_HOURS = _bounded_env_int(
        'KUBERNETES_SECRET_REVEAL_PENDING_TTL_HOURS',
        24,
        1,
        168,
    )

    APP_NAME = 'KAORI'

    APP_VERSION = _env_str(
        'APP_VERSION',
        '1.0.0',
    )
    APP_BUILD_SHA = _env_optional_str('APP_BUILD_SHA')
    APP_BUILD_DATE = _env_optional_str('APP_BUILD_DATE')

    # Reusable archive storage profile. The unified Activity Audit Log uses
    # this profile now; reports and future domains can reuse the same Local/S3
    # lifecycle without introducing parallel retention implementations.
    ARCHIVE_STORAGE_BACKEND = _normalize_storage_backend(
        _env_str(
            'ARCHIVE_STORAGE_BACKEND',
            _env_str('REPORT_STORAGE_BACKEND', 'local'),
        )
    )
    ARCHIVE_LOCAL_STORAGE_DIR = _resolve_path(
        _env_str(
            'ARCHIVE_LOCAL_STORAGE_DIR',
            _env_str('REPORT_LOCAL_STORAGE_DIR', 'instance'),
        ),
        BASE_DIR / 'instance',
    )
    ARCHIVE_DOWNLOAD_CACHE_DIR = _resolve_path(
        _env_str('ARCHIVE_DOWNLOAD_CACHE_DIR', 'instance/archive-download-cache'),
        BASE_DIR / 'instance' / 'archive-download-cache',
    )
    ARCHIVE_STAGING_DIR = _resolve_path(
        _env_str('ARCHIVE_STAGING_DIR', 'instance/archive-staging'),
        BASE_DIR / 'instance' / 'archive-staging',
    )
    ARCHIVE_OBJECT_PREFIX = _env_str('ARCHIVE_OBJECT_PREFIX', 'archives').strip().strip('/')
    ARCHIVE_SCHEDULED_DOMAINS = tuple(
        item.strip().lower().replace('-', '_')
        for item in _env_str(
            'ARCHIVE_SCHEDULED_DOMAINS', 'operational_activity,job_execution,runtime_observation'
        ).split(',')
        if item.strip()
    )
    ARCHIVE_S3_BUCKET = _env_str('ARCHIVE_S3_BUCKET', _env_str('REPORT_S3_BUCKET', ''))
    ARCHIVE_S3_REGION = _env_str('ARCHIVE_S3_REGION', _env_str('REPORT_S3_REGION', 'us-east-1'))
    ARCHIVE_S3_ACCESS_KEY_ID = _env_optional_str('ARCHIVE_S3_ACCESS_KEY_ID') or _env_optional_str(
        'REPORT_S3_ACCESS_KEY_ID'
    )
    ARCHIVE_S3_SECRET_ACCESS_KEY = _env_optional_str('ARCHIVE_S3_SECRET_ACCESS_KEY') or _env_optional_str(
        'REPORT_S3_SECRET_ACCESS_KEY'
    )
    ARCHIVE_S3_ENDPOINT_URL = _env_optional_str('ARCHIVE_S3_ENDPOINT_URL') or _env_optional_str(
        'REPORT_S3_ENDPOINT_URL'
    )
    ARCHIVE_S3_PREFIX = _env_str('ARCHIVE_S3_PREFIX', _env_str('REPORT_S3_PREFIX', '')).strip().strip('/')
    ARCHIVE_S3_FORCE_PATH_STYLE = _env_bool(
        'ARCHIVE_S3_FORCE_PATH_STYLE',
        _env_bool('REPORT_S3_FORCE_PATH_STYLE', False),
    )

    # Operational Activity archive-first retention policy.
    ACTIVITY_RETENTION_ENABLED = _env_bool('ACTIVITY_RETENTION_ENABLED', True)
    ACTIVITY_RETENTION_DAYS = _env_int('ACTIVITY_RETENTION_DAYS', 90)
    ACTIVITY_ARCHIVE_RETENTION_DAYS = _env_int('ACTIVITY_ARCHIVE_RETENTION_DAYS', 365)
    ACTIVITY_RETENTION_BATCH_SIZE = _env_int('ACTIVITY_RETENTION_BATCH_SIZE', 5000)
    ACTIVITY_RETENTION_PROTECT_UNREVIEWED = _env_bool('ACTIVITY_RETENTION_PROTECT_UNREVIEWED', False)
    ACTIVITY_RETENTION_PROTECTED_MAX_DAYS = _env_int('ACTIVITY_RETENTION_PROTECTED_MAX_DAYS', 180)
    ACTIVITY_RETENTION_SCHEDULE_ENABLED = _env_bool('ACTIVITY_RETENTION_SCHEDULE_ENABLED', True)
    ACTIVITY_RETENTION_SCHEDULE_HOUR = _bounded_env_int('ACTIVITY_RETENTION_SCHEDULE_HOUR', 2, 0, 23)
    ACTIVITY_RETENTION_SCHEDULE_MINUTE = _bounded_env_int('ACTIVITY_RETENTION_SCHEDULE_MINUTE', 15, 0, 59)

    # Canonical JobExecution archive-first retention policy.
    JOB_EXECUTION_RETENTION_ENABLED = _env_bool('JOB_EXECUTION_RETENTION_ENABLED', True)
    JOB_EXECUTION_RETENTION_DAYS = _env_int('JOB_EXECUTION_RETENTION_DAYS', 90)
    JOB_EXECUTION_ARCHIVE_RETENTION_DAYS = _env_int('JOB_EXECUTION_ARCHIVE_RETENTION_DAYS', 365)
    JOB_EXECUTION_RETENTION_BATCH_SIZE = _env_int('JOB_EXECUTION_RETENTION_BATCH_SIZE', 2500)
    JOB_EXECUTION_RUNTIME_RETENTION_DAYS = _env_int('JOB_EXECUTION_RUNTIME_RETENTION_DAYS', 30)
    JOB_EXECUTION_VALIDATION_RETENTION_DAYS = _env_int('JOB_EXECUTION_VALIDATION_RETENTION_DAYS', 30)
    JOB_EXECUTION_ANALYTICS_RETENTION_DAYS = _env_int('JOB_EXECUTION_ANALYTICS_RETENTION_DAYS', 90)
    JOB_EXECUTION_FORECASTING_RETENTION_DAYS = _env_int('JOB_EXECUTION_FORECASTING_RETENTION_DAYS', 180)
    JOB_EXECUTION_FAILED_RETENTION_DAYS = _env_int('JOB_EXECUTION_FAILED_RETENTION_DAYS', 90)
    JOB_EXECUTION_RETENTION_SCHEDULE_HOUR = _bounded_env_int('JOB_EXECUTION_RETENTION_SCHEDULE_HOUR', 3, 0, 23)
    JOB_EXECUTION_RETENTION_SCHEDULE_MINUTE = _bounded_env_int('JOB_EXECUTION_RETENTION_SCHEDULE_MINUTE', 0, 0, 59)

    # Provider runtime observation archive-first retention policy.
    RUNTIME_OBSERVATION_RETENTION_ENABLED = _env_bool('RUNTIME_OBSERVATION_RETENTION_ENABLED', True)
    RUNTIME_OBSERVATION_RETENTION_DAYS = _env_int('RUNTIME_OBSERVATION_RETENTION_DAYS', 90)
    RUNTIME_OBSERVATION_ARCHIVE_RETENTION_DAYS = _env_int('RUNTIME_OBSERVATION_ARCHIVE_RETENTION_DAYS', 365)
    RUNTIME_OBSERVATION_RETENTION_BATCH_SIZE = _env_int('RUNTIME_OBSERVATION_RETENTION_BATCH_SIZE', 5000)
    RUNTIME_OBSERVATION_RETENTION_SCHEDULE_HOUR = _bounded_env_int(
        'RUNTIME_OBSERVATION_RETENTION_SCHEDULE_HOUR', 3, 0, 23
    )
    RUNTIME_OBSERVATION_RETENTION_SCHEDULE_MINUTE = _bounded_env_int(
        'RUNTIME_OBSERVATION_RETENTION_SCHEDULE_MINUTE', 45, 0, 59
    )

    REPORT_SCHEDULE_TIMEZONE = _env_str(
        'REPORT_SCHEDULE_TIMEZONE',
        'Asia/Jakarta',
    )

    # Reports storage.
    # Supported values:
    # - local: local filesystem in the application/instance folder
    # - s3: S3-compatible object storage, including AWS S3 and MinIO
    REPORT_STORAGE_BACKEND = _normalize_storage_backend(
        _env_str(
            'REPORT_STORAGE_BACKEND',
            'local',
        )
    )

    # Local backend root directory. Object keys are stored under this root.
    # With REPORT_LOCAL_STORAGE_DIR=instance and object key reports/YYYY/MM/...
    # files are stored under: <project-root>/instance/reports/YYYY/MM/...
    REPORT_LOCAL_STORAGE_DIR = _resolve_path(
        _env_str(
            'REPORT_LOCAL_STORAGE_DIR',
            'instance',
        ),
        BASE_DIR / 'instance',
    )

    # Temporary staging directory used while rendering PDFs before they are
    # copied/uploaded to the configured storage backend.
    REPORT_RENDER_STAGING_DIR = _resolve_path(
        _env_str(
            'REPORT_RENDER_STAGING_DIR',
            'instance/report-render-staging',
        ),
        BASE_DIR / 'instance' / 'report-render-staging',
    )

    # Download cache for object-storage backends. Local backend does not need
    # this, but keeping it configurable helps later S3/MinIO testing.
    REPORT_DOWNLOAD_CACHE_DIR = _resolve_path(
        _env_str(
            'REPORT_DOWNLOAD_CACHE_DIR',
            'instance/report-download-cache',
        ),
        BASE_DIR / 'instance' / 'report-download-cache',
    )

    # S3-compatible backend configuration.
    # AWS S3: leave REPORT_S3_ENDPOINT_URL empty.
    # MinIO: set REPORT_S3_ENDPOINT_URL, for example http://minio:9000.
    REPORT_S3_BUCKET = _env_str(
        'REPORT_S3_BUCKET',
        '',
    )

    REPORT_S3_REGION = _env_str(
        'REPORT_S3_REGION',
        'us-east-1',
    )

    REPORT_S3_ACCESS_KEY_ID = _env_optional_str(
        'REPORT_S3_ACCESS_KEY_ID',
    )

    REPORT_S3_SECRET_ACCESS_KEY = _env_optional_str(
        'REPORT_S3_SECRET_ACCESS_KEY',
    )

    REPORT_S3_ENDPOINT_URL = _env_optional_str(
        'REPORT_S3_ENDPOINT_URL',
    )

    # Optional root prefix inside bucket. Keep empty by default because the
    # generated object key already starts with reports/YYYY/MM/...
    REPORT_S3_PREFIX = (
        _env_str(
            'REPORT_S3_PREFIX',
            '',
        )
        .strip()
        .strip('/')
    )

    REPORT_S3_FORCE_PATH_STYLE = _env_bool(
        'REPORT_S3_FORCE_PATH_STYLE',
        False,
    )

    # Report artifact retention and cleanup policy. MVP2 defines the policy and
    # exposes dry-run visibility in the UI; destructive deletion remains guarded
    # unless REPORT_DESTRUCTIVE_CLEANUP_ENABLED is explicitly enabled later.
    REPORT_RETENTION_DAYS = _env_int(
        'REPORT_RETENTION_DAYS',
        90,
    )

    REPORT_ARCHIVE_RETENTION_DAYS = _env_int(
        'REPORT_ARCHIVE_RETENTION_DAYS',
        180,
    )

    REPORT_CLEANUP_MODE = _env_str(
        'REPORT_CLEANUP_MODE',
        'dry-run-only',
    )

    REPORT_CLEANUP_SCOPE = _env_str(
        'REPORT_CLEANUP_SCOPE',
        'ready-and-archived-artifacts',
    )

    REPORT_ORPHAN_DETECTION_ENABLED = _env_bool(
        'REPORT_ORPHAN_DETECTION_ENABLED',
        True,
    )

    REPORT_DESTRUCTIVE_CLEANUP_ENABLED = _env_bool(
        'REPORT_DESTRUCTIVE_CLEANUP_ENABLED',
        False,
    )
