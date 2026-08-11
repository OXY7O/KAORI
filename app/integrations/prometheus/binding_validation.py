from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.binding_selectors import selector_is_configured
from app.integrations.prometheus.binding_profiles import get_binding_validation_profile
from app.integrations.prometheus.client import PrometheusClient
from app.integrations.prometheus.exceptions import PrometheusError
from app.models.integration import IntegrationBinding
from app.models.prometheus import PrometheusInstance


def validate_binding(
    *,
    instance: PrometheusInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    """Validate one Prometheus asset selector through its registered probe profile."""
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Prometheus source.')
    if not selector_is_configured(binding.selector_json):
        binding.validation_status = 'blocked'
        binding.validation_message = 'Configure a metrics identity selector before validating this binding.'
        binding.last_validated_at = datetime.now(UTC)
        if commit:
            db.session.commit()
        return {
            'status': binding.validation_status,
            'message': binding.validation_message,
            'matched_series': 0,
            'matched_signal': None,
            'probe_profile': None,
            'probe_results': [],
        }

    profile = get_binding_validation_profile(binding.asset_type)
    if profile is None:
        binding.validation_status = 'blocked'
        binding.validation_message = (
            f'No Prometheus binding validation profile is registered for asset type {binding.asset_type!r}.'
        )
        binding.last_validated_at = datetime.now(UTC)
        if commit:
            db.session.commit()
        return {
            'status': binding.validation_status,
            'message': binding.validation_message,
            'matched_series': 0,
            'matched_signal': None,
            'probe_profile': None,
            'probe_results': [],
        }

    probe_results: list[dict[str, Any]] = []
    matched_signal: str | None = None
    matched = 0.0
    try:
        client = PrometheusClient(
            instance,
            scope_selector=binding.selector_json,
            request_timeout_seconds=max(int(instance.timeout or 5), 15),
        )
        for probe in profile.probes:
            payload = client.query(f'count({probe.metric})')
            if not isinstance(payload, dict) or payload.get('status') != 'success':
                detail = (
                    str((payload or {}).get('error') or 'Prometheus returned an unsuccessful query response.')
                    if isinstance(payload, dict)
                    else 'Prometheus returned an invalid query response.'
                )
                raise PrometheusError(detail)
            result = (payload.get('data') or {}).get('result') or []
            value = 0.0
            if result and isinstance(result[0], dict):
                sample = result[0].get('value') or []
                if len(sample) > 1:
                    value = float(sample[1])
            probe_results.append(
                {
                    'metric': probe.metric,
                    'label': probe.label,
                    'matched_series': int(value),
                }
            )
            if value > 0 and matched_signal is None:
                matched_signal = probe.metric
                matched = value

        if matched_signal is not None:
            binding.validation_status = 'ready'
            binding.validation_message = (
                f'{profile.label} matched {int(matched)} scoped series through {matched_signal}.'
            )
        else:
            binding.validation_status = 'degraded'
            binding.validation_message = profile.no_match_message
    except Exception as exc:
        binding.validation_status = 'blocked'
        binding.validation_message = f'Binding validation failed: {exc}'
        matched = 0.0
        matched_signal = None

    binding.last_validated_at = datetime.now(UTC)
    if commit:
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'matched_series': int(matched),
        'matched_signal': matched_signal,
        'probe_profile': binding.asset_type,
        'probe_results': probe_results,
    }
