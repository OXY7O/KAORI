from __future__ import annotations

import re
from typing import Any

from app.integrations.binding_selectors import BindingMatcher, parse_matchers
from app.integrations.observability.metrics_source.binding_profiles import BindingValidationProfile
from app.integrations.observability.metrics_source.binding_validators.contracts import BindingValidationAssessment
from app.integrations.observability.metrics_source.exceptions import MetricsQueryError, MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles.audit import PromQLProfileAuditor
from app.models.integration import IntegrationBinding


def validate_kubernetes_binding(
    *,
    client: Any,
    binding: IntegrationBinding,
    profile: BindingValidationProfile,
) -> BindingValidationAssessment:
    identity_contract = _source_identity_contract(client, binding)
    if identity_contract['status'] != 'ready':
        return BindingValidationAssessment(
            status='degraded',
            message=str(identity_contract['message']),
            evidence={
                'source_identity': identity_contract,
                'probe_results': [],
                'available_capabilities': [],
                'capability_assessments': [],
            },
        )

    probe_results: list[dict[str, Any]] = []
    matched_signal: str | None = None
    matched_series = 0

    for probe in profile.probes:
        payload = client.query(probe.expression)
        if not isinstance(payload, dict) or payload.get('status') != 'success':
            raise MetricsQueryError('Metrics Source returned an unsuccessful identity-probe response.')
        result = (payload.get('data') or {}).get('result') or []
        value = 0
        if result and isinstance(result[0], dict):
            sample = result[0].get('value') or []
            if len(sample) > 1:
                value = int(float(sample[1]))
        probe_results.append(
            {
                'signal_key': probe.signal_key,
                'expression': probe.expression,
                'label': probe.label,
                'matched_series': value,
            }
        )
        if value > 0 and matched_signal is None:
            matched_signal = probe.signal_key
            matched_series = value

    if matched_signal is None:
        return BindingValidationAssessment(
            status='degraded',
            message=profile.no_match_message,
            evidence={
                'source_identity': identity_contract,
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
            'KAORI will evaluate those gaps per downstream consumer instead of degrading the shared Metrics Source runtime.'
        )
    )
    return BindingValidationAssessment(
        status='ready',
        message=message,
        matched_series=matched_series,
        matched_signal=matched_signal,
        available_capabilities=tuple(consumer_audit.get('available_capabilities') or ()),
        evidence={
            'source_identity': identity_contract,
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


def _source_identity_contract(client: Any, binding: IntegrationBinding) -> dict[str, Any]:
    matchers = parse_matchers(binding.selector_json)
    if not matchers:
        return _identity_result(
            'failed',
            'Metrics source identity selector is not configured.',
            expected='Kubernetes bindings require cluster=<stable-cluster-name>.',
            observed='No binding selector was configured.',
            recommendation='Set the binding selector label to cluster and use the exact query-visible cluster value exposed by this metrics source.',
        )

    cluster_matcher = next((matcher for matcher in matchers if matcher.label == 'cluster'), None)
    if cluster_matcher is None:
        configured = ', '.join(matcher.label for matcher in matchers)
        return _identity_result(
            'failed',
            'Kubernetes metrics bindings require the canonical cluster source label.',
            expected='cluster=<stable-cluster-name>',
            observed=f'Configured selector label(s): {configured or "none"}.',
            recommendation='Use cluster as the Kubernetes Metrics Source binding label and expose the same query-visible cluster label on Prometheus/Thanos series.',
        )

    try:
        payload = client.label_values(cluster_matcher.label)
    except MetricsSourceError as exc:
        return _identity_result(
            'failed',
            'KAORI could not inspect the mandatory cluster source label.',
            expected=f'cluster{cluster_matcher.operator}"{cluster_matcher.value}"',
            observed=f'Label discovery failed: {type(exc).__name__}: {exc}',
            recommendation='Restore label-discovery API access, then rerun binding validation.',
        )

    values = (
        [str(value) for value in (payload.get('data') or []) if str(value)]
        if payload.get('status') == 'success'
        else []
    )
    if not values:
        return _identity_result(
            'failed',
            'Mandatory cluster source label is missing from the configured metrics endpoint.',
            expected=f'cluster{cluster_matcher.operator}"{cluster_matcher.value}"',
            observed='The /api/v1/label/cluster/values response contained no values.',
            recommendation=_cluster_identity_recommendation(client),
        )

    if not _matcher_has_value(cluster_matcher, values):
        preview = ', '.join(values[:5])
        return _identity_result(
            'failed',
            'The cluster label exists, but the binding value does not match any observed source identity.',
            expected=f'cluster{cluster_matcher.operator}"{cluster_matcher.value}"',
            observed=f'Observed cluster values: {preview or "none"}.',
            recommendation='Make the Metrics Source binding selector value exactly match the stable cluster external label, then rerun validation.',
        )

    return _identity_result(
        'ready',
        'Canonical cluster source identity is available for the Kubernetes binding.',
        expected=f'cluster{cluster_matcher.operator}"{cluster_matcher.value}"',
        observed=f'Observed {len(values)} cluster label value(s); the configured selector matches.',
        recommendation='No source-identity remediation is required.',
    )


def _cluster_identity_recommendation(client: Any) -> str:
    provider_key = str(getattr(getattr(client, 'config', None), 'provider_key', '') or '').strip().lower()
    if provider_key == 'thanos':
        return (
            'Set cluster=<stable-cluster-name> as an external label on every source Prometheus so Thanos exposes '
            'the cluster identity, then rerun binding validation.'
        )
    return (
        'Add cluster=<stable-cluster-name> as a query-visible target label to the Kubernetes scrape pipelines '
        '(kube-state-metrics, node-exporter, and kubelet/cAdvisor). If this Prometheus also feeds Thanos, set the '
        'same value in Prometheus external labels, then rerun binding validation.'
    )


def _matcher_has_value(matcher: BindingMatcher, values: list[str]) -> bool:
    if matcher.operator == '=':
        return matcher.value in values
    if matcher.operator == '!=':
        return any(value != matcher.value for value in values)
    try:
        pattern = re.compile(matcher.value)
    except re.error:
        return False
    if matcher.operator == '=~':
        return any(pattern.fullmatch(value) for value in values)
    if matcher.operator == '!~':
        return any(not pattern.fullmatch(value) for value in values)
    return False


def _identity_result(
    status: str,
    message: str,
    *,
    expected: str,
    observed: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        'key': 'source_identity.cluster',
        'label': 'Cluster Source Identity',
        'status': status,
        'status_label': 'Ready' if status == 'ready' else 'Failed',
        'message': message,
        'expected': expected,
        'observed': observed,
        'recommendation': recommendation,
        'technical_checks': [
            {
                'key': 'cluster_source_label',
                'label': 'cluster source label',
                'status': status,
                'status_label': 'Ready' if status == 'ready' else 'Failed',
                'evidence': observed,
            }
        ],
    }
