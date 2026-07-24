from __future__ import annotations

from typing import Any

from app.extensions.db import db
from app.integrations.alertmanager.client_factory import build_client
from app.integrations.alertmanager.status import mark_status
from app.models.alertmanager import AlertmanagerInstance


def refresh_instance_health(instance: AlertmanagerInstance) -> dict[str, Any]:
    """Refresh Alertmanager reachability without rebuilding capability evidence."""
    try:
        result = build_client(instance).test_connection()
    except Exception as exc:
        mark_status(
            instance,
            status='disconnected',
            error=str(exc),
            response_time_ms=None,
            commit=True,
        )
        raise

    instance.detected_version = str(result.get('version') or instance.detected_version or 'unknown')
    mark_status(
        instance,
        status='connected',
        error=None,
        response_time_ms=int(result.get('response_time_ms') or 0),
        commit=False,
    )
    if not instance.readiness_status:
        instance.readiness_status = 'validation_required'
        instance.validation_message = (
            'Runtime health is available. Run Full Validation to establish capability evidence.'
        )
    db.session.commit()
    return result
