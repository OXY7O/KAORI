from __future__ import annotations

from time import perf_counter
from typing import Any

from app.extensions.db import db
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.integrations.registry.providers.harbor.exceptions import HarborError
from app.integrations.registry.providers.harbor.status import mark_status
from app.models.harbor import HarborInstance


def refresh_instance_health(instance: HarborInstance) -> dict[str, Any]:
    """Refresh Harbor health without rebuilding compatibility/capability evidence."""
    started = perf_counter()
    try:
        health = build_client(instance).get_health()
    except HarborError as exc:
        mark_status(
            instance,
            status='disconnected',
            error=str(exc),
            response_time_ms=None,
            commit=True,
        )
        raise

    elapsed_ms = int((perf_counter() - started) * 1000)
    overall = str(health.get('status') or 'unknown')
    components = []
    raw_components = health.get('components')
    if isinstance(raw_components, list):
        for item in raw_components:
            if isinstance(item, dict):
                components.append(
                    {
                        'name': str(item.get('name') or 'unknown'),
                        'status': str(item.get('status') or 'unknown'),
                    }
                )

    summary = dict(instance.validation_summary or {})
    summary['runtime_health'] = {'status': overall, 'components': components}
    instance.validation_summary = summary
    mark_status(
        instance,
        status='connected',
        error=None,
        response_time_ms=elapsed_ms,
        commit=False,
    )
    if not instance.readiness_status:
        instance.readiness_status = 'validation_required'
        instance.validation_message = (
            'Runtime health is available. Run Full Validation to establish compatibility and capability evidence.'
        )
    db.session.commit()
    return {
        'connected': True,
        'health_status': overall,
        'components': components,
        'response_time_ms': elapsed_ms,
    }
