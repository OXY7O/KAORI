import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from dotenv import dotenv_values

from app.notification_channels.config import build_notification_beat_schedule

BASE_DIR = Path(__file__).resolve().parents[2]


def _load_environment_files() -> None:
    """Load .env and optional .env.<APP_ENV> without overriding real OS env vars.

    Precedence:
    1. OS environment variables
    2. .env.<APP_ENV> values
    3. .env values
    """
    base_values = dotenv_values(BASE_DIR / '.env')
    app_env = os.getenv('APP_ENV') or base_values.get('APP_ENV') or 'development'
    environment_values = dotenv_values(BASE_DIR / f'.env.{app_env}')
    merged_values = {**base_values, **environment_values}

    for key, value in merged_values.items():
        if value is not None:
            os.environ.setdefault(key, value)


def _env_str(name: str, default: str = '') -> str:
    return os.getenv(name, default)


def _env_optional_str(name: str) -> str | None:
    value = os.getenv(name, '').strip()
    return value or None


def _env_int(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(_env_int(name, default), maximum))


def _retention_queue_name() -> str:
    return _env_str('RETENTION_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'


def _build_maintenance_beat_schedule() -> dict[str, dict[str, object]]:
    schedule: dict[str, dict[str, object]] = {}
    if _env_bool('DATA_LIFECYCLE_SCHEDULER_ENABLED', True):
        schedule['data-lifecycle-dispatcher'] = {
            'task': 'app.retention.tasks.run_scheduled_retention',
            'schedule': crontab(minute='*/15'),
            'options': {'queue': _retention_queue_name()},
        }
    if _env_bool('JOB_POLICY_SCHEDULER_ENABLED', True):
        schedule['job-policy-dispatcher'] = {
            'task': 'app.jobs.tasks.dispatch_scheduled_jobs',
            'schedule': crontab(minute='*'),
            'options': {
                'queue': (_env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'),
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
    schedule.update(build_notification_beat_schedule())
    if _env_bool('JOB_RECOVERY_ENABLED', True):
        schedule['job-execution-recovery'] = {
            'task': 'app.jobs.tasks.reconcile_stale_jobs',
            'schedule': crontab(minute=f'*/{_bounded_env_int("JOB_RECOVERY_INTERVAL_MINUTES", 5, 1, 60)}'),
            'options': {
                'queue': (_env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'),
            },
        }
    if _env_bool('AUTOMATION_CANDIDATE_MATERIALIZATION_ENABLED', True):
        schedule['automation-candidate-materialization'] = {
            'task': 'app.automation_control.tasks.materialize_automation_candidates',
            'schedule': crontab(
                minute=f'*/{_bounded_env_int("AUTOMATION_CANDIDATE_MATERIALIZATION_INTERVAL_MINUTES", 1, 1, 60)}'
            ),
            'options': {'queue': (_env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance')},
        }
    if _env_bool('AUTOMATION_LIFECYCLE_RECONCILIATION_ENABLED', True):
        schedule['automation-lifecycle-reconciliation'] = {
            'task': 'app.automation_control.tasks.reconcile_automation_lifecycle',
            'schedule': crontab(minute='*'),
            'options': {'queue': (_env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance')},
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
    if _env_bool('REPORT_STORAGE_HEALTH_MONITOR_ENABLED', True):
        schedule['report-storage-readiness'] = {
            'task': 'app.reports.storage.tasks.refresh_report_storage_readiness_task',
            'schedule': crontab(minute=f'*/{_bounded_env_int("REPORT_STORAGE_HEALTH_INTERVAL_MINUTES", 1, 1, 60)}'),
            'options': {
                'queue': _env_str('REPORT_STORAGE_HEALTH_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'
            },
        }
    return schedule


def _normalize_storage_backend(value: str | None) -> str:
    backend = (value or 'local').strip().lower()
    return backend if backend in {'local', 's3'} else 'local'


def _resolve_path(value: str | None, default: Path) -> str:
    path = Path((value or str(default)).strip())
    return str(path if path.is_absolute() else BASE_DIR / path)


def _object_storage_usage_stats_mode() -> str:
    mode = _env_str('OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE', 'disabled').strip().lower()
    return mode if mode in {'disabled', 'provider_metrics', 'full_scan'} else 'disabled'


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
        18000,
    )

    CLUSTER_SYNC_LOCK_TTL_SECONDS = _env_int(
        'CLUSTER_SYNC_LOCK_TTL_SECONDS',
        10800,
    )
    CLUSTER_SYNC_COMPLETED_TTL_SECONDS = _env_int(
        'CLUSTER_SYNC_COMPLETED_TTL_SECONDS',
        300,
    )
    OBJECT_STORAGE_INVENTORY_USAGE_STATS_MODE = _object_storage_usage_stats_mode()
    TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS = _bounded_env_int(
        'TLS_CERTIFICATE_RENEWAL_WINDOW_DAYS',
        30,
        1,
        365,
    )
    TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS = _bounded_env_int(
        'TLS_CERTIFICATE_CRITICAL_WINDOW_DAYS',
        7,
        1,
        365,
    )

    CELERY_TIMEZONE = _env_str(
        'CELERY_TIMEZONE',
        'UTC',
    )
    RETENTION_CELERY_QUEUE = _retention_queue_name()
    RETENTION_RETRY_DELAY_SECONDS = _bounded_env_int('RETENTION_RETRY_DELAY_SECONDS', 60, 1, 3600)
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
    REPORTS_CELERY_QUEUE = _env_str('REPORTS_CELERY_QUEUE', 'reports').strip() or 'reports'
    REPORT_STORAGE_HEALTH_MONITOR_ENABLED = _env_bool('REPORT_STORAGE_HEALTH_MONITOR_ENABLED', True)
    REPORT_STORAGE_HEALTH_INTERVAL_MINUTES = _bounded_env_int('REPORT_STORAGE_HEALTH_INTERVAL_MINUTES', 1, 1, 60)
    REPORT_STORAGE_HEALTH_STALE_SECONDS = _bounded_env_int('REPORT_STORAGE_HEALTH_STALE_SECONDS', 120, 30, 3600)
    REPORT_STORAGE_HEALTH_STATE_TTL_SECONDS = _bounded_env_int(
        'REPORT_STORAGE_HEALTH_STATE_TTL_SECONDS', 600, 120, 86400
    )
    REPORT_STORAGE_HEALTH_CELERY_QUEUE = (
        _env_str('REPORT_STORAGE_HEALTH_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'
    )
    KAORI_PUBLIC_BASE_URL = _env_str('KAORI_PUBLIC_BASE_URL', '').strip()
    ANALYTICS_TASK_SOFT_TIME_LIMIT_SECONDS = _bounded_env_int('ANALYTICS_TASK_SOFT_TIME_LIMIT_SECONDS', 900, 60, 7200)
    ANALYTICS_TASK_HARD_TIME_LIMIT_SECONDS = _bounded_env_int('ANALYTICS_TASK_HARD_TIME_LIMIT_SECONDS', 960, 120, 7260)
    ANALYTICS_TASK_MAX_SOFT_TIME_LIMIT_SECONDS = _bounded_env_int(
        'ANALYTICS_TASK_MAX_SOFT_TIME_LIMIT_SECONDS', 7200, 900, 7200
    )
    ANALYTICS_DATASET_TIMEOUT_SECONDS = _bounded_env_int('ANALYTICS_DATASET_TIMEOUT_SECONDS', 300, 30, 1800)
    FORECASTING_TASK_SOFT_TIME_LIMIT_SECONDS = _bounded_env_int(
        'FORECASTING_TASK_SOFT_TIME_LIMIT_SECONDS', 2700, 300, 14400
    )
    FORECASTING_TASK_HARD_TIME_LIMIT_SECONDS = _bounded_env_int(
        'FORECASTING_TASK_HARD_TIME_LIMIT_SECONDS', 2760, 360, 14460
    )
    FORECASTING_TASK_MAX_SOFT_TIME_LIMIT_SECONDS = _bounded_env_int(
        'FORECASTING_TASK_MAX_SOFT_TIME_LIMIT_SECONDS', 14400, 2700, 14400
    )
    FORECASTING_DATASET_TIMEOUT_SECONDS = _bounded_env_int('FORECASTING_DATASET_TIMEOUT_SECONDS', 600, 60, 3600)
    PROMETHEUS_ANALYTICS_QUERY_TIMEOUT_SECONDS = _bounded_env_int(
        'PROMETHEUS_ANALYTICS_QUERY_TIMEOUT_SECONDS', 30, 5, 120
    )
    PROMETHEUS_ANALYTICS_RANGE_QUERY_TIMEOUT_SECONDS = _bounded_env_int(
        'PROMETHEUS_ANALYTICS_RANGE_QUERY_TIMEOUT_SECONDS', 120, 15, 300
    )
    PROMETHEUS_ANALYTICS_QUERY_RETRIES = _bounded_env_int('PROMETHEUS_ANALYTICS_QUERY_RETRIES', 2, 0, 5)
    PROMETHEUS_ANALYTICS_RETRY_BACKOFF_SECONDS = _bounded_env_int(
        'PROMETHEUS_ANALYTICS_RETRY_BACKOFF_SECONDS', 1, 0, 10
    )
    ANALYTICS_SOURCE_LOCK_TIMEOUT_SECONDS = _bounded_env_int('ANALYTICS_SOURCE_LOCK_TIMEOUT_SECONDS', 900, 5, 1800)
    JOB_MAINTENANCE_CELERY_QUEUE = _env_str('JOB_MAINTENANCE_CELERY_QUEUE', 'maintenance').strip() or 'maintenance'
    AUTOMATION_EXECUTION_ENABLED = _env_bool('AUTOMATION_EXECUTION_ENABLED', False)
    CUSTOM_RUNBOOK_AUTHORING_ENABLED = _env_bool('CUSTOM_RUNBOOK_AUTHORING_ENABLED', False)
    AUTOMATION_CANDIDATE_MATERIALIZATION_ENABLED = _env_bool('AUTOMATION_CANDIDATE_MATERIALIZATION_ENABLED', True)
    AUTOMATION_CANDIDATE_MATERIALIZATION_INTERVAL_MINUTES = _bounded_env_int(
        'AUTOMATION_CANDIDATE_MATERIALIZATION_INTERVAL_MINUTES', 1, 1, 60
    )
    AUTOMATION_LIFECYCLE_RECONCILIATION_ENABLED = _env_bool('AUTOMATION_LIFECYCLE_RECONCILIATION_ENABLED', True)
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
            'app.alert_delivery.tasks',
            'app.automation_control.tasks',
            'app.analytics.kubernetes.tasks',
            'app.analytics.object_storage.tasks',
            'app.cluster.tasks',
            'app.inventory.object_storage.tasks',
            'app.governance.tls_certificates.tasks',
            'app.retention.tasks',
            'app.integrations.runtime.tasks',
            'app.integrations.validation.tasks',
            'app.jobs.tasks',
            'app.reports.schedules.tasks',
            'app.reports.jobs.tasks',
            'app.reports.storage.tasks',
            'app.resolver.tasks',
        ),
        'task_routes': {
            'app.analytics.kubernetes.tasks.materialize_analytics_snapshots': {
                'queue': ANALYTICS_CELERY_QUEUE,
            },
            'app.analytics.kubernetes.tasks.materialize_forecast_snapshots': {
                'queue': FORECASTING_CELERY_QUEUE,
            },
            'app.analytics.object_storage.tasks.materialize_object_storage_forecasts': {
                'queue': FORECASTING_CELERY_QUEUE,
            },
            'app.cluster.tasks.sync_all_clusters': {
                'queue': 'inventory',
            },
            'app.cluster.tasks.sync_single_cluster': {
                'queue': 'inventory',
            },
            'app.inventory.object_storage.tasks.sync_all_object_storage': {
                'queue': 'inventory',
            },
            'app.governance.tls_certificates.tasks.sync_tls_certificates': {
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
            'app.alert_delivery.tasks.dispatch_alert_intelligence_notifications': {
                'queue': JOB_MAINTENANCE_CELERY_QUEUE,
            },
            'app.automation_control.tasks.dispatch_automation_decision_notification': {
                'queue': JOB_MAINTENANCE_CELERY_QUEUE,
            },
            'app.resolver.tasks.dispatch_resolver_execution_notification': {
                'queue': JOB_MAINTENANCE_CELERY_QUEUE,
            },
            'app.automation_control.tasks.materialize_automation_candidates': {
                'queue': JOB_MAINTENANCE_CELERY_QUEUE,
            },
            'app.automation_control.tasks.reconcile_automation_lifecycle': {
                'queue': JOB_MAINTENANCE_CELERY_QUEUE,
            },
            'app.reports.schedules.tasks.run_report_schedule_job': {
                'queue': REPORTS_CELERY_QUEUE,
            },
            'app.reports.jobs.tasks.generate_report_job': {
                'queue': REPORTS_CELERY_QUEUE,
            },
            'app.reports.storage.tasks.refresh_report_storage_readiness_task': {
                'queue': REPORT_STORAGE_HEALTH_CELERY_QUEUE,
            },
            'app.resolver.tasks.execute_authorized_resolution': {
                'queue': RESOLVER_EXECUTION_CELERY_QUEUE,
            },
            'app.resolver.tasks.verify_authorized_resolution': {
                'queue': RESOLVER_MAINTENANCE_CELERY_QUEUE,
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

    AUTH_REMEMBER_ME_DAYS = _bounded_env_int(
        'AUTH_REMEMBER_ME_DAYS',
        7,
        1,
        30,
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=AUTH_REMEMBER_ME_DAYS)

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
        '2.2.0',
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
    ARCHIVE_PURGE_BATCH_SIZE = _bounded_env_int('ARCHIVE_PURGE_BATCH_SIZE', 250, 25, 2500)
    DATA_LIFECYCLE_SCHEDULER_ENABLED = _env_bool('DATA_LIFECYCLE_SCHEDULER_ENABLED', True)
    ARCHIVE_SCHEDULED_DOMAINS = tuple(
        item.strip().lower().replace('-', '_')
        for item in _env_str(
            'ARCHIVE_SCHEDULED_DOMAINS',
            'operational_activity,job_execution,runtime_observation,analytics_snapshot,generated_report',
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

    # Reusable AnalyticsSnapshot archive-first retention policy.
    ANALYTICS_SNAPSHOT_RETENTION_ENABLED = _env_bool('ANALYTICS_SNAPSHOT_RETENTION_ENABLED', True)
    ANALYTICS_SNAPSHOT_RETENTION_DAYS = _env_int('ANALYTICS_SNAPSHOT_RETENTION_DAYS', 30)
    ANALYTICS_SNAPSHOT_ARCHIVE_RETENTION_DAYS = _env_int('ANALYTICS_SNAPSHOT_ARCHIVE_RETENTION_DAYS', 180)
    ANALYTICS_SNAPSHOT_RETENTION_BATCH_SIZE = _env_int('ANALYTICS_SNAPSHOT_RETENTION_BATCH_SIZE', 5000)
    ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_HOUR = _bounded_env_int(
        'ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_HOUR', 4, 0, 23
    )
    ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_MINUTE = _bounded_env_int(
        'ANALYTICS_SNAPSHOT_RETENTION_SCHEDULE_MINUTE', 15, 0, 59
    )

    # Generated Report archive-first retention policy. Ready report metadata and
    # binary artifacts are archived together before hot storage cleanup.
    GENERATED_REPORT_RETENTION_ENABLED = _env_bool('GENERATED_REPORT_RETENTION_ENABLED', False)
    GENERATED_REPORT_RETENTION_DAYS = _env_int(
        'GENERATED_REPORT_RETENTION_DAYS',
        _env_int('REPORT_RETENTION_DAYS', 90),
    )
    GENERATED_REPORT_ARCHIVE_RETENTION_DAYS = _env_int(
        'GENERATED_REPORT_ARCHIVE_RETENTION_DAYS',
        _env_int('REPORT_ARCHIVE_RETENTION_DAYS', 365),
    )
    GENERATED_REPORT_RETENTION_BATCH_SIZE = _env_int('GENERATED_REPORT_RETENTION_BATCH_SIZE', 250)
    GENERATED_REPORT_FAILED_RETENTION_DAYS = _env_int('GENERATED_REPORT_FAILED_RETENTION_DAYS', 30)
    GENERATED_REPORT_ARCHIVED_RETENTION_DAYS = _env_int('GENERATED_REPORT_ARCHIVED_RETENTION_DAYS', 180)
    GENERATED_REPORT_RETENTION_SCHEDULE_HOUR = _bounded_env_int('GENERATED_REPORT_RETENTION_SCHEDULE_HOUR', 5, 0, 23)
    GENERATED_REPORT_RETENTION_SCHEDULE_MINUTE = _bounded_env_int(
        'GENERATED_REPORT_RETENTION_SCHEDULE_MINUTE', 0, 0, 59
    )

    REPORT_SCHEDULE_TIMEZONE = _env_str(
        'REPORT_SCHEDULE_TIMEZONE',
        'Asia/Jakarta',
    )

    REPORT_PDF_CLASSIFICATION = (
        _env_str(
            'REPORT_PDF_CLASSIFICATION',
            'Internal',
        ).strip()
        or 'Internal'
    )

    # Reports storage supports local filesystem and S3-compatible backends (AWS S3/MinIO).
    REPORT_STORAGE_BACKEND = _normalize_storage_backend(
        _env_str(
            'REPORT_STORAGE_BACKEND',
            'local',
        )
    )

    # Local backend root; report object keys are stored beneath this directory.
    REPORT_LOCAL_STORAGE_DIR = _resolve_path(
        _env_str(
            'REPORT_LOCAL_STORAGE_DIR',
            'instance',
        ),
        BASE_DIR / 'instance',
    )

    # Temporary staging directory used before rendered PDFs reach the storage backend.
    REPORT_RENDER_STAGING_DIR = _resolve_path(
        _env_str(
            'REPORT_RENDER_STAGING_DIR',
            'instance/report-render-staging',
        ),
        BASE_DIR / 'instance' / 'report-render-staging',
    )

    # Download cache for object-storage backends; local storage does not require it.
    REPORT_DOWNLOAD_CACHE_DIR = _resolve_path(
        _env_str(
            'REPORT_DOWNLOAD_CACHE_DIR',
            'instance/report-download-cache',
        ),
        BASE_DIR / 'instance' / 'report-download-cache',
    )

    # S3-compatible backend: leave endpoint empty for AWS S3; set it for MinIO.
    REPORT_S3_BUCKET = _env_str('REPORT_S3_BUCKET', '')
    REPORT_S3_REGION = _env_str('REPORT_S3_REGION', 'us-east-1')
    REPORT_S3_ACCESS_KEY_ID = _env_optional_str('REPORT_S3_ACCESS_KEY_ID')
    REPORT_S3_SECRET_ACCESS_KEY = _env_optional_str('REPORT_S3_SECRET_ACCESS_KEY')
    REPORT_S3_ENDPOINT_URL = _env_optional_str('REPORT_S3_ENDPOINT_URL')

    # Optional root prefix inside bucket. Keep empty by default because the
    # generated object key already starts with reports/YYYY/MM/...
    REPORT_S3_PREFIX = _env_str('REPORT_S3_PREFIX', '').strip().strip('/')
    REPORT_S3_FORCE_PATH_STYLE = _env_bool('REPORT_S3_FORCE_PATH_STYLE', False)

    REPORT_S3_CONNECT_TIMEOUT_SECONDS = _bounded_env_int('REPORT_S3_CONNECT_TIMEOUT_SECONDS', 2, 1, 30)
    REPORT_S3_READ_TIMEOUT_SECONDS = _bounded_env_int('REPORT_S3_READ_TIMEOUT_SECONDS', 3, 1, 60)
    REPORT_S3_MAX_ATTEMPTS = _bounded_env_int('REPORT_S3_MAX_ATTEMPTS', 1, 1, 5)
    REPORT_STORAGE_STATUS_CACHE_SECONDS = _bounded_env_int('REPORT_STORAGE_STATUS_CACHE_SECONDS', 15, 0, 300)

    # Legacy report-retention age keys remain as compatibility fallbacks for
    # deployments upgrading to the Generated Reports Data Lifecycle domain.
    # Execution mode and destructive cleanup are owned only by Data Lifecycle.
    REPORT_RETENTION_DAYS = _env_int('REPORT_RETENTION_DAYS', 90)
    REPORT_ARCHIVE_RETENTION_DAYS = _env_int('REPORT_ARCHIVE_RETENTION_DAYS', 180)
    REPORT_ORPHAN_DETECTION_ENABLED = _env_bool('REPORT_ORPHAN_DETECTION_ENABLED', True)
