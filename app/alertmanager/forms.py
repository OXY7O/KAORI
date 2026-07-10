from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

ALLOWED_AUTH_TYPES = {
    'none',
    'basic',
    'bearer',
}


@dataclass(frozen=True)
class AlertmanagerConfigForm:
    endpoint: str
    auth_type: str
    username: str | None
    password: str | None
    bearer_token: str | None
    timeout: int
    verify_ssl: bool


def parse_alertmanager_config_form(
    form_data: Mapping[str, Any],
) -> AlertmanagerConfigForm:
    endpoint = normalize_endpoint(
        str(
            form_data.get(
                'endpoint',
                '',
            )
        ).strip()
    )

    auth_type = str(
        form_data.get(
            'auth_type',
            'none',
        )
    ).strip()

    if auth_type not in ALLOWED_AUTH_TYPES:
        auth_type = 'none'

    username = clean_optional_value(
        form_data.get(
            'username',
        )
    )
    password = clean_optional_value(
        form_data.get(
            'password',
        )
    )
    bearer_token = clean_optional_value(
        form_data.get(
            'bearer_token',
        )
    )
    timeout = parse_timeout(
        form_data.get(
            'timeout',
            5,
        )
    )
    verify_ssl = parse_checkbox(
        form_data.get(
            'verify_ssl',
        )
    )

    return AlertmanagerConfigForm(
        endpoint=endpoint,
        auth_type=auth_type,
        username=username,
        password=password,
        bearer_token=bearer_token,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )


def normalize_endpoint(
    value: str,
) -> str:
    endpoint = value.rstrip(
        '/',
    )

    if not endpoint:
        return ''

    if not endpoint.startswith(
        (
            'http://',
            'https://',
        )
    ):
        return f'http://{endpoint}'

    return endpoint


def clean_optional_value(
    value: Any,
) -> str | None:
    if value is None:
        return None

    cleaned = str(
        value,
    ).strip()

    if not cleaned:
        return None

    return cleaned


def parse_timeout(
    value: Any,
) -> int:
    try:
        timeout = int(
            value,
        )
    except (
        TypeError,
        ValueError,
    ):
        return 5

    if timeout < 1:
        return 1

    if timeout > 5:
        return 5

    return timeout


def parse_checkbox(
    value: Any,
) -> bool:
    return str(
        value,
    ).lower() in {
        '1',
        'true',
        'on',
        'yes',
    }
