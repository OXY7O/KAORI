from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.alertmanager.client_factory import build_client
from app.integrations.binding_selectors import selector_filters
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding


def validate_binding(
    *,
    instance: AlertmanagerInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Alertmanager source.')

    filters = list(selector_filters(binding.selector_json))
    if binding.asset_type != 'global' and not filters:
        binding.validation_status = 'blocked'
        binding.validation_message = 'Configure an alert identity selector before validating this binding.'
        binding.last_validated_at = datetime.now(UTC)
        if commit:
            db.session.commit()
        return {
            'status': binding.validation_status,
            'message': binding.validation_message,
            'matched_alerts': 0,
        }

    try:
        alerts = build_client(instance).get_alerts(filters=filters)
        binding.validation_status = 'ready'
        binding.validation_message = (
            f'Alertmanager accepted the scope filter and returned {len(alerts)} active alert records.'
        )
        matched = len(alerts)
    except Exception as exc:
        binding.validation_status = 'blocked'
        binding.validation_message = f'Binding validation failed: {exc}'
        matched = 0

    binding.last_validated_at = datetime.now(UTC)
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'matched_alerts': matched,
    }
