from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.binding_selectors import selector_is_configured
from app.integrations.prometheus.binding_profiles import get_binding_validation_profile
from app.integrations.prometheus.client import PrometheusClient
from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles.audit import PromQLProfileAuditor
from app.models.integration import IntegrationBinding
from app.models.prometheus import PrometheusInstance

_KUBERNETES_CONSUMER_PROFILE = 'kubernetes-metrics-v1'


def validate_binding(
    *,
    instance: PrometheusInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    """Validate one Prometheus consumer binding through its registered profile."""
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

    binding.validation_profile = profile.profile_key
    probe_results: list[dict[str, Any]] = []
    matched_signal: str | None = None
    matched = 0.0
    consumer_audit: dict[str, Any] | None = None
    try:
        client = PrometheusClient(
            instance,
            scope_selector=binding.selector_json,
            request_timeout_seconds=max(int(instance.timeout or 5), 30),
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

        if matched_signal is None:
            binding.validation_status = 'degraded'
            binding.validation_message = profile.no_match_message
        elif profile.profile_key == _KUBERNETES_CONSUMER_PROFILE:
            consumer_audit = PromQLProfileAuditor(client).audit(execute_queries=True)
            contract_summary = consumer_audit.get('feature_contract_summary') or {}
            contract_status = str(contract_summary.get('status') or 'validation_required')
            binding.validation_status = 'ready'
            binding.validation_message = (
                f'{profile.label} matched the scoped Kubernetes identity and collected consumer capability evidence.'
                if contract_status == 'ready'
                else (
                    f'{profile.label} matched scoped Kubernetes metrics and collected consumer evidence with capability gaps. '
                    'KAORI will evaluate those gaps per downstream consumer instead of degrading the shared Prometheus runtime.'
                )
            )
        else:
            binding.validation_status = 'ready'
            binding.validation_message = (
                f'{profile.label} matched {int(matched)} scoped series through {matched_signal}.'
            )
    except Exception as exc:
        binding.validation_status = 'blocked'
        binding.validation_message = f'Binding validation failed: {exc}'
        matched = 0.0
        matched_signal = None
        consumer_audit = None

    binding.validation_evidence = _validation_evidence(
        profile_key=profile.profile_key,
        profile_label=profile.label,
        consumer_family=profile.consumer_family,
        probe_results=probe_results,
        matched_signal=matched_signal,
        matched_series=int(matched),
        consumer_audit=consumer_audit,
    )
    binding.last_validated_at = datetime.now(UTC)
    if commit:
        _commit_or_rollback()
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'matched_series': int(matched),
        'matched_signal': matched_signal,
        'probe_profile': profile.profile_key,
        'probe_profile_label': profile.label,
        'consumer_family': profile.consumer_family,
        'available_capabilities': list((binding.validation_evidence or {}).get('available_capabilities') or ()),
        'probe_results': probe_results,
    }


def _validation_evidence(
    *,
    profile_key: str,
    profile_label: str,
    consumer_family: str,
    probe_results: list[dict[str, Any]],
    matched_signal: str | None,
    matched_series: int,
    consumer_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        'profile_key': profile_key,
        'profile_label': profile_label,
        'consumer_family': consumer_family,
        'matched_signal': matched_signal,
        'matched_series': matched_series,
        'probe_results': probe_results,
        'available_capabilities': [],
        'capability_assessments': [],
    }
    if consumer_audit:
        evidence.update(
            {
                'query_profile': consumer_audit.get('profile'),
                'available_capabilities': consumer_audit.get('available_capabilities', []),
                'capability_assessments': consumer_audit.get('capability_assessments', []),
                'feature_contract_summary': consumer_audit.get('feature_contract_summary') or {},
                'module_readiness': consumer_audit.get('module_readiness') or {},
                'retention': consumer_audit.get('retention') or {},
                'checked_at': consumer_audit.get('checked_at'),
            }
        )
    return evidence


def _persist_blocked(binding: IntegrationBinding, *, message: str, commit: bool) -> dict[str, Any]:
    binding.validation_status = 'blocked'
    binding.validation_profile = None
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
        'probe_profile': None,
        'probe_profile_label': None,
        'consumer_family': None,
        'available_capabilities': [],
        'probe_results': [],
    }


def _commit_or_rollback() -> None:
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
