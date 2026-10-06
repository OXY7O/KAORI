from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.binding_selectors import selector_filters, selector_is_configured, selector_summary
from app.integrations.observability.alert_source.providers.alertmanager.binding_profiles import (
    get_alert_consumer_profile,
)
from app.integrations.observability.alert_source.providers.alertmanager.client_factory import build_client
from app.integrations.observability.alert_source.providers.alertmanager.exceptions import AlertmanagerError
from app.integrations.observability.alert_source.providers.alertmanager.probes import discover_payload_capabilities
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding


def validate_binding(
    *,
    instance: AlertmanagerInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    """Validate one Alertmanager consumer binding without changing provider readiness."""
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Alertmanager source.')

    profile = get_alert_consumer_profile(binding.asset_type)
    if profile is None:
        return _persist_blocked(
            binding,
            message=f'No Alertmanager consumer profile is registered for asset type {binding.asset_type!r}.',
            commit=commit,
        )

    if binding.asset_type != 'global' and not selector_is_configured(binding.selector_json):
        return _persist_blocked(
            binding,
            profile_key=profile.profile_key,
            message='Configure an alert identity selector before validating this consumer binding.',
            commit=commit,
        )

    filters = list(selector_filters(binding.selector_json))
    binding.validation_profile = profile.profile_key
    matched_alerts = 0
    available_capabilities: set[str] = {'alerts_v2'}
    alerts: list[dict[str, Any]] = []
    silences: list[dict[str, Any]] = []

    try:
        client = build_client(instance)
        payload = client.get_alerts(filters=filters)
        alerts = payload if isinstance(payload, list) else []
        silence_payload = client.get_silences(filters=filters)
        silences = silence_payload if isinstance(silence_payload, list) else []
        matched_alerts = len(alerts)
        available_capabilities.add('silences_v2')
        available_capabilities.update(discover_payload_capabilities(alerts, silences))

        missing_required = tuple(
            capability for capability in profile.required_capabilities if capability not in available_capabilities
        )
        if binding.asset_type != 'global' and not alerts:
            binding.validation_status = 'ready'
            binding.validation_message = (
                f'{profile.label} accepted the governed selector. No active alert currently matches it, '
                'so payload-label evidence will be refreshed when representative alerts are available.'
            )
        elif missing_required:
            binding.validation_status = 'degraded'
            binding.validation_message = (
                f'{profile.label} matched active alerts but is missing required consumer evidence: '
                f'{", ".join(missing_required)}.'
            )
        else:
            binding.validation_status = 'ready'
            binding.validation_message = (
                f'{profile.label} validated {matched_alerts} scoped active alert record'
                f'{"" if matched_alerts == 1 else "s"}.'
                if binding.asset_type != 'global'
                else f'{profile.label} validated the unscoped Alerts API consumer contract.'
            )
    except AlertmanagerError as exc:
        binding.validation_status = 'blocked'
        binding.validation_message = f'Consumer binding validation failed: {exc}'
        missing_required = tuple(profile.required_capabilities)
        alerts = []
        silences = []
        matched_alerts = 0
        available_capabilities = set()

    binding.validation_evidence = {
        'profile_key': profile.profile_key,
        'profile_label': profile.label,
        'consumer_family': profile.consumer_family,
        'selector': selector_summary(binding.selector_json),
        'selector_hint': profile.selector_hint,
        'matched_alerts': matched_alerts,
        'matched_silences': len(silences),
        'required_capabilities': list(profile.required_capabilities),
        'optional_capabilities': list(profile.optional_capabilities),
        'available_capabilities': sorted(available_capabilities),
        'missing_required_capabilities': list(missing_required),
        'sample_alert_names': _sample_alert_names(alerts),
        'identity_observed': bool(alerts) if binding.asset_type != 'global' else True,
    }
    binding.last_validated_at = datetime.now(UTC)
    if commit:
        _commit_or_rollback()
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'matched_alerts': matched_alerts,
        'matched_silences': len(silences),
        'consumer_profile': profile.profile_key,
        'consumer_profile_label': profile.label,
        'available_capabilities': sorted(available_capabilities),
        'missing_required_capabilities': list(missing_required),
    }


def _sample_alert_names(alerts: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for alert in alerts[:5]:
        labels = alert.get('labels') if isinstance(alert, dict) else None
        if isinstance(labels, dict) and labels.get('alertname'):
            names.append(str(labels['alertname']))
    return names


def _persist_blocked(
    binding: IntegrationBinding,
    *,
    message: str,
    commit: bool,
    profile_key: str | None = None,
) -> dict[str, Any]:
    binding.validation_status = 'blocked'
    binding.validation_profile = profile_key
    binding.validation_evidence = None
    binding.validation_message = message
    binding.last_validated_at = datetime.now(UTC)
    if commit:
        _commit_or_rollback()
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'matched_alerts': 0,
        'consumer_profile': profile_key,
        'consumer_profile_label': None,
        'available_capabilities': [],
        'missing_required_capabilities': [],
    }


def _commit_or_rollback() -> None:
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
