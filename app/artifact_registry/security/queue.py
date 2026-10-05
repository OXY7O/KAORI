from __future__ import annotations

from flask import current_app

DEFAULT_REGISTRY_SECURITY_QUEUE = 'registry-security'


def get_registry_security_queue_name() -> str:
    """Return the provider-neutral queue used by Artifact Registry security work."""

    configured_queue = current_app.config.get(
        'REGISTRY_SECURITY_CELERY_QUEUE',
        DEFAULT_REGISTRY_SECURITY_QUEUE,
    )
    return str(configured_queue or DEFAULT_REGISTRY_SECURITY_QUEUE).strip() or DEFAULT_REGISTRY_SECURITY_QUEUE
