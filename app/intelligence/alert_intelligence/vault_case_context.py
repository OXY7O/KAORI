"""Redacted same-instance runtime context for a qualified Vault provider case.

The caller owns the audited exact-instance case read transaction. This
projection never loads Vault credentials, diagnostic payloads or fleet data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.intelligence.alert_signals.vault_source import _persisted_utc
from app.models.integration import IntegrationInstance
from app.models.runtime import IntegrationRuntimeObservation

_HEALTH = {
    'healthy': ('Healthy', 'normal'),
    'degraded': ('Degraded', 'warning'),
    'unhealthy': ('Unhealthy', 'critical'),
}
_READINESS = {
    'ready': 'Ready',
    'degraded': 'Degraded',
    'validation_required': 'Validation Required',
    'blocked': 'Blocked',
}


def _unavailable(label: str) -> dict[str, Any]:
    return {
        'status': label,
        'tone': 'unknown',
        'readiness': None,
        'observed_at': None,
        'score': None,
    }


def read_vault_case_runtime_context(instance_id: int) -> dict[str, Any]:
    """Use only the latest committed runtime row of the exact canonical instance.

    No older healthy fallback after an invalid latest observation. The
    timestamp is historical context, not a current health or recovery claim.
    """
    instance = db.session.get(IntegrationInstance, instance_id, populate_existing=True)
    if (
        instance is None
        or instance.integration_type != 'secrets_pki'
        or instance.provider_key != 'vault'
        or not instance.enabled
        or instance.lifecycle_status != 'active'
    ):
        return _unavailable('Evidence Unavailable')
    row = (
        db.session.query(
            IntegrationRuntimeObservation.integration_type,
            IntegrationRuntimeObservation.provider_key,
            IntegrationRuntimeObservation.adapter_key,
            IntegrationRuntimeObservation.readiness,
            IntegrationRuntimeObservation.health_status,
            IntegrationRuntimeObservation.health_score,
            IntegrationRuntimeObservation.observed_at,
            IntegrationRuntimeObservation.created_at,
        )
        .filter(IntegrationRuntimeObservation.integration_instance_id == instance_id)
        .order_by(IntegrationRuntimeObservation.observed_at.desc(), IntegrationRuntimeObservation.id.desc())
        .first()
    )
    if row is None:
        return _unavailable('Not Observed')
    observed = _persisted_utc(row.observed_at)
    committed = _persisted_utc(row.created_at)
    if (
        row.integration_type != 'secrets_pki'
        or row.provider_key != 'vault'
        or row.adapter_key != instance.adapter_key
        or observed is None
        or committed is None
        or not observed <= committed <= datetime.now(UTC)
        or row.health_status not in _HEALTH
        or row.readiness not in _READINESS
        or type(row.health_score) is not int
        or not 0 <= row.health_score <= 100
    ):
        return _unavailable('Evidence Unavailable')
    status, tone = _HEALTH[row.health_status]
    return {
        'status': status,
        'tone': tone,
        'readiness': _READINESS[row.readiness],
        'observed_at': observed,
        'score': row.health_score,
    }
