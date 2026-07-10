import os
from pathlib import Path

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

    SQLALCHEMY_DATABASE_URI = _env_str(
        'DATABASE_URL',
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = _env_optional_str(
        'REDIS_URL',
    )

    WTF_CSRF_ENABLED = True

    # Authentication providers.
    # Database login is always enabled as the local break-glass admin provider.
    # Optional external providers can be enabled later when implemented.
    # Supported future values: ldap, sso. Example: ldap,sso.
    AUTH_ADDITIONAL_PROVIDERS = (
        _env_str(
            'AUTH_ADDITIONAL_PROVIDERS',
            '',
        )
        .strip()
        .lower()
    )

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

    # Login audit retention. The Login Activity UI shows the latest matching
    # records, while this value controls how long audit rows are kept before
    # cleanup-login-audit removes old entries.
    AUTH_LOGIN_AUDIT_RETENTION_DAYS = _env_int(
        'AUTH_LOGIN_AUDIT_RETENTION_DAYS',
        90,
    )

    APP_NAME = 'KAORI'

    APP_VERSION = '1.0.0'

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

    # Backward-compatible alias for older report storage code.
    REPORT_STORAGE_ROOT_DIR = REPORT_LOCAL_STORAGE_DIR

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
