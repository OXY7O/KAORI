from __future__ import annotations

from typing import Any

from app.integrations.prometheus.binding_profiles import BindingValidationProfile
from app.integrations.prometheus.binding_validators.contracts import BindingValidationAssessment
from app.integrations.prometheus.exceptions import PrometheusQueryError
from app.integrations.prometheus.query_profiles.audit import PromQLProfileAuditor
from app.models.integration import IntegrationBinding


def validate_kubernetes_binding(
    *,
    client: Any,
    binding: IntegrationBinding,
    profile: BindingValidationProfile,
) -> BindingValidationAssessment:
    probe_results: list[dict[str, Any]] = []
    matched_signal: str | None = None
    matched_series = 0

    for probe in profile.probes:
        payload = client.query(f'count({probe.metric})')
        if not isinstance(payload, dict) or payload.get('status') != 'success':
            raise PrometheusQueryError('Prometheus returned an unsuccessful identity-probe response.')
        result = (payload.get('data') or {}).get('result') or []
        value = 0
        if result and isinstance(result[0], dict):
            sample = result[0].get('value') or []
            if len(sample) > 1:
                value = int(float(sample[1]))
        probe_results.append(
            {
                'metric': probe.metric,
                'label': probe.label,
                'matched_series': value,
            }
        )
        if value > 0 and matched_signal is None:
            matched_signal = probe.metric
            matched_series = value

    if matched_signal is None:
        return BindingValidationAssessment(
            status='degraded',
            message=profile.no_match_message,
            evidence={
                'probe_results': probe_results,
                'available_capabilities': [],
                'capability_assessments': [],
            },
        )

    consumer_audit = PromQLProfileAuditor(client).audit(execute_queries=True)
    contract_summary = consumer_audit.get('feature_contract_summary') or {}
    contract_status = str(contract_summary.get('status') or 'validation_required')
    message = (
        f'{profile.label} matched the scoped Kubernetes identity and collected consumer capability evidence.'
        if contract_status == 'ready'
        else (
            f'{profile.label} matched scoped Kubernetes metrics and collected consumer evidence with capability gaps. '
            'KAORI will evaluate those gaps per downstream consumer instead of degrading the shared Prometheus runtime.'
        )
    )
    return BindingValidationAssessment(
        status='ready',
        message=message,
        matched_series=matched_series,
        matched_signal=matched_signal,
        available_capabilities=tuple(consumer_audit.get('available_capabilities') or ()),
        evidence={
            'probe_results': probe_results,
            'query_profile': consumer_audit.get('profile'),
            'available_capabilities': consumer_audit.get('available_capabilities', []),
            'capability_assessments': consumer_audit.get('capability_assessments', []),
            'feature_contract_summary': consumer_audit.get('feature_contract_summary') or {},
            'module_readiness': consumer_audit.get('module_readiness') or {},
            'retention': consumer_audit.get('retention') or {},
            'checked_at': consumer_audit.get('checked_at'),
        },
    )
