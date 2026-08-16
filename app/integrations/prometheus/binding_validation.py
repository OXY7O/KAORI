from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.binding_selectors import selector_is_configured
from app.integrations.prometheus.binding_profiles import BindingValidationProfile, get_binding_validation_profile
from app.integrations.prometheus.binding_validators import get_binding_validator
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
    """Validate one Prometheus consumer binding through its canonical consumer validator."""
    if instance.integration_instance_id != binding.integration_instance_id:
        raise ValueError('The selected binding does not belong to this Prometheus source.')
    if not selector_is_configured(binding.selector_json):
        return _persist_blocked(
            binding,
            message='Configure a metrics identity selector before validating this binding.',
            commit=commit,
        )

    profile = get_binding_validation_profile(binding.asset_type)
    if profile is None:
        return _persist_blocked(
            binding,
            message=f'No Prometheus consumer validation profile is registered for asset type {binding.asset_type!r}.',
            commit=commit,
        )

    validator = get_binding_validator(binding.asset_type)
    if validator is None:
        return _persist_blocked(
            binding,
            profile_key=profile.profile_key,
            message=f'No Prometheus consumer validator is registered for asset type {binding.asset_type!r}.',
            commit=commit,
        )

    binding.validation_profile = profile.profile_key
    attempted_at = datetime.now(UTC)
    matched_series = 0
    matched_signal: str | None = None
    available_capabilities: tuple[str, ...] = ()
    probe_results: list[dict[str, Any]] = []
    try:
        client = PrometheusClient(
            instance,
            scope_selector=binding.selector_json,
            request_timeout_seconds=max(int(instance.timeout or 5), 30),
        )
        assessment = validator(client=client, binding=binding, profile=profile)
        binding.validation_status = assessment.status
        binding.validation_message = assessment.message
        matched_series = assessment.matched_series
        matched_signal = assessment.matched_signal
        available_capabilities = assessment.available_capabilities
        probe_results = list(assessment.evidence.get('probe_results') or ())
        binding.validation_evidence = _validation_evidence(
            profile=profile,
            matched_signal=assessment.matched_signal,
            matched_series=assessment.matched_series,
            available_capabilities=assessment.available_capabilities,
            evidence=assessment.evidence,
            attempted_at=attempted_at,
            attempt_status=assessment.status,
        )
    except PrometheusError as exc:
        binding.validation_status = 'blocked'
        binding.validation_message = f'Binding validation failed: {exc}'
        binding.validation_evidence = _validation_failure_evidence(
            previous=binding.validation_evidence,
            profile=profile,
            error=str(exc),
            attempted_at=attempted_at,
        )

    binding.last_validated_at = attempted_at
    if commit:
        _commit_or_rollback()
    evidence = binding.validation_evidence or {}
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'matched_series': matched_series,
        'matched_signal': matched_signal,
        'probe_profile': profile.profile_key,
        'probe_profile_label': profile.label,
        'consumer_family': profile.consumer_family,
        'available_capabilities': list(available_capabilities),
        'probe_results': probe_results,
        'metrics_readiness': evidence.get('metrics_readiness') or {},
    }


def _validation_evidence(
    *,
    profile: BindingValidationProfile,
    matched_signal: str | None,
    matched_series: int,
    available_capabilities: tuple[str, ...],
    evidence: dict[str, Any],
    attempted_at: datetime,
    attempt_status: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'profile_key': profile.profile_key,
        'profile_label': profile.label,
        'consumer_family': profile.consumer_family,
        'matched_signal': matched_signal,
        'matched_series': matched_series,
        'available_capabilities': list(available_capabilities),
        'capability_assessments': [],
        'last_validation_attempt': {
            'status': attempt_status,
            'checked_at': attempted_at.isoformat(),
            'error': None,
        },
    }
    payload.update(evidence)
    payload.pop('runtime_error', None)
    return payload


def _validation_failure_evidence(
    *,
    previous: dict[str, Any] | None,
    profile: BindingValidationProfile,
    error: str,
    attempted_at: datetime,
) -> dict[str, Any]:
    previous_payload = previous if isinstance(previous, dict) else {}
    payload = dict(previous_payload) if previous_payload.get('profile_key') == profile.profile_key else {}
    payload.update(
        {
            'profile_key': profile.profile_key,
            'profile_label': profile.label,
            'consumer_family': profile.consumer_family,
            'runtime_error': error,
            'last_validation_attempt': {
                'status': 'blocked',
                'checked_at': attempted_at.isoformat(),
                'error': error,
            },
        }
    )
    payload.setdefault('matched_signal', None)
    payload.setdefault('matched_series', 0)
    payload.setdefault('available_capabilities', [])
    payload.setdefault('capability_assessments', [])
    return payload


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
        'matched_series': 0,
        'matched_signal': None,
        'probe_profile': profile_key,
        'probe_profile_label': None,
        'consumer_family': None,
        'available_capabilities': [],
        'probe_results': [],
        'metrics_readiness': {},
    }


def _commit_or_rollback() -> None:
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
