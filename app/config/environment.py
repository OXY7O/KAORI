from __future__ import annotations

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
