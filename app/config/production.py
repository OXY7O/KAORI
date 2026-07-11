from __future__ import annotations

import os

from app.config.default import Config


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {
        '1',
        'true',
        'yes',
        'y',
        'on',
    }


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return max(int(value.strip()), 0)
    except ValueError:
        return default


def _env_csv(name: str) -> list[str] | None:
    values = [value.strip() for value in os.getenv(name, '').split(',') if value.strip()]
    return values or None


class ProductionConfig(Config):
    DEBUG = False

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

    PREFERRED_URL_SCHEME = 'https'
    TRUSTED_HOSTS = _env_csv('TRUSTED_HOSTS')

    PROXY_FIX_ENABLED = _env_bool(
        'PROXY_FIX_ENABLED',
        True,
    )
    PROXY_FIX_X_FOR = _env_int('PROXY_FIX_X_FOR', 1)
    PROXY_FIX_X_PROTO = _env_int('PROXY_FIX_X_PROTO', 1)
    PROXY_FIX_X_HOST = _env_int('PROXY_FIX_X_HOST', 1)
    PROXY_FIX_X_PORT = _env_int('PROXY_FIX_X_PORT', 1)
    PROXY_FIX_X_PREFIX = _env_int('PROXY_FIX_X_PREFIX', 0)

    REPORT_STORAGE_BACKEND = (
        os.getenv(
            'PROD_REPORT_STORAGE_BACKEND',
            Config.REPORT_STORAGE_BACKEND,
        )
        .strip()
        .lower()
    )

    REPORT_LOCAL_STORAGE_DIR = os.getenv(
        'PROD_REPORT_LOCAL_STORAGE_DIR',
        Config.REPORT_LOCAL_STORAGE_DIR,
    )

    REPORT_S3_BUCKET = os.getenv(
        'PROD_REPORT_S3_BUCKET',
        Config.REPORT_S3_BUCKET,
    )

    REPORT_S3_REGION = os.getenv(
        'PROD_REPORT_S3_REGION',
        Config.REPORT_S3_REGION,
    )

    REPORT_S3_ACCESS_KEY_ID = (
        os.getenv(
            'PROD_REPORT_S3_ACCESS_KEY_ID',
            Config.REPORT_S3_ACCESS_KEY_ID or '',
        )
        or None
    )

    REPORT_S3_SECRET_ACCESS_KEY = (
        os.getenv(
            'PROD_REPORT_S3_SECRET_ACCESS_KEY',
            Config.REPORT_S3_SECRET_ACCESS_KEY or '',
        )
        or None
    )

    REPORT_S3_ENDPOINT_URL = (
        os.getenv(
            'PROD_REPORT_S3_ENDPOINT_URL',
            Config.REPORT_S3_ENDPOINT_URL or '',
        )
        or None
    )

    REPORT_S3_PREFIX = (
        os.getenv(
            'PROD_REPORT_S3_PREFIX',
            Config.REPORT_S3_PREFIX,
        )
        .strip()
        .strip('/')
    )
