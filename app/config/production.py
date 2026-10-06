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
