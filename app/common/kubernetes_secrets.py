from __future__ import annotations

from typing import Any


def scrub_mapping_values(payload: dict[Any, Any] | None) -> None:
    if not isinstance(payload, dict):
        return
    for key in list(payload):
        payload[key] = ''
    payload.clear()


def scrub_secret_payload(secret: Any) -> None:
    """Best-effort removal of Kubernetes Secret material from an in-memory object."""
    if secret is None:
        return
    for attribute in ('data', 'string_data'):
        value = getattr(secret, attribute, None)
        scrub_mapping_values(value if isinstance(value, dict) else None)
        try:
            setattr(secret, attribute, None)
        except (AttributeError, TypeError):
            pass
