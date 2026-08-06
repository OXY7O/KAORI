from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from app.integrations.prometheus.exceptions import PrometheusError
from app.integrations.prometheus.query_profiles import get_query


@dataclass(frozen=True, slots=True)
class FeatureContract:
    key: str
    feature: str
    label: str
    query_keys: tuple[str, ...]
    expected: str
    allow_empty: bool = False
    required_labels: tuple[str, ...] = ()


FEATURE_CONTRACTS: tuple[FeatureContract, ...] = (
    FeatureContract(
        'capacity.cpu',
        'Capacity Analytics',
        'CPU Capacity Contract',
        ('analytics.utilization.queries.CPU_CAPACITY',),
        'The analytics query returns a positive numeric CPU capacity value.',
    ),
    FeatureContract(
        'capacity.memory',
        'Capacity Analytics',
        'Memory Capacity Contract',
        ('analytics.utilization.queries.MEMORY_CAPACITY',),
        'The analytics query returns a positive numeric memory capacity value.',
    ),
    FeatureContract(
        'capacity.worker',
        'Capacity Analytics',
        'Worker Capacity Contract',
        ('analytics.capacity.queries.CURRENT_WORKER_PODS_QUERY', 'analytics.capacity.queries.WORKER_CPU_USAGE_QUERY'),
        'The worker discovery and worker usage queries execute successfully and return usable values.',
    ),
    FeatureContract(
        'utilization.cpu',
        'Utilization Analytics',
        'CPU Utilization Contract',
        ('analytics.utilization.queries.CPU_UTILIZATION',),
        'The exact CPU utilization query executes successfully and returns a numeric value.',
    ),
    FeatureContract(
        'utilization.memory',
        'Utilization Analytics',
        'Memory Utilization Contract',
        ('analytics.utilization.queries.MEMORY_UTILIZATION',),
        'The exact memory utilization query executes successfully and returns a numeric value.',
    ),
    FeatureContract(
        'utilization.storage',
        'Utilization Analytics',
        'Storage Utilization Contract',
        ('analytics.utilization.queries.STORAGE_UTILIZATION',),
        'The exact storage utilization query executes successfully and returns a numeric value.',
        allow_empty=True,
    ),
    FeatureContract(
        'storage.filesystem',
        'Storage Analytics',
        'Storage Filesystem Contract',
        (
            'analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY',
            'analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY',
            'analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY',
            'analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY',
        ),
        'Either the /var pair or the / pair returns usable filesystem series with canonical node identity.',
        required_labels=('node|nodename|kubernetes_node',),
    ),
    FeatureContract(
        'storage.pvc',
        'Storage Analytics',
        'PVC Usage Contract',
        (
            'analytics.storage.queries.PVC_CAPACITY_BY_CLAIM_QUERY',
            'analytics.storage.queries.PVC_USED_BY_CLAIM_QUERY',
            'analytics.storage.queries.PVC_AVAILABLE_BY_CLAIM_QUERY',
        ),
        'PVC observed capacity, used, and available queries execute successfully. An empty result is valid when no active PVC is observed.',
        allow_empty=True,
    ),
    FeatureContract(
        'workload.namespace',
        'Workload Analytics',
        'Namespace Contract',
        ('analytics.workload.queries.NAMESPACE_ACTIVE_QUERY',),
        'The namespace query executes successfully and returns observable namespaces.',
        allow_empty=True,
    ),
    FeatureContract(
        'workload.owner',
        'Workload Analytics',
        'Workload Owner Mapping Contract',
        ('analytics.workload.queries.WORKLOAD_POD_OWNER_QUERY',),
        'The exact workload owner query executes successfully. Empty is reported as Not Observed, not Missing.',
        allow_empty=True,
    ),
    FeatureContract(
        'workload.qos',
        'Workload Analytics',
        'Workload QoS Contract',
        ('analytics.workload.queries.WORKLOAD_QOS_QUERY',),
        'The exact QoS query executes successfully. Empty is reported as Not Observed.',
        allow_empty=True,
    ),
    FeatureContract(
        'workload.resources',
        'Workload Analytics',
        'Requests and Limits Contract',
        (
            'analytics.workload.queries.WORKLOAD_CPU_REQUESTS_QUERY',
            'analytics.workload.queries.WORKLOAD_CPU_LIMITS_QUERY',
        ),
        'The exact workload request and limit queries execute successfully.',
        allow_empty=True,
    ),
    FeatureContract(
        'forecast.cpu',
        'Forecast Analytics',
        'CPU Forecast Input Contract',
        ('analytics.forecast.queries.CPU_USAGE_QUERY', 'analytics.forecast.queries.CPU_WORKER_CAPACITY_QUERY'),
        'Current CPU usage and capacity queries execute successfully before range-history validation.',
    ),
    FeatureContract(
        'forecast.memory',
        'Forecast Analytics',
        'Memory Forecast Input Contract',
        ('analytics.forecast.queries.MEMORY_USAGE_QUERY', 'analytics.forecast.queries.MEMORY_WORKER_CAPACITY_QUERY'),
        'Current memory usage and capacity queries execute successfully before range-history validation.',
    ),
    FeatureContract(
        'forecast.pods',
        'Forecast Analytics',
        'Pod Forecast Input Contract',
        ('analytics.forecast.queries.POD_USAGE_QUERY', 'analytics.forecast.queries.POD_WORKER_CAPACITY_QUERY'),
        'Active Pending or Running Pod demand and Ready-worker Pod capacity queries execute successfully before range-history validation.',
        allow_empty=True,
    ),
    FeatureContract(
        'forecast.storage',
        'Forecast Analytics',
        'Storage Forecast Input Contract',
        ('analytics.forecast.queries.STORAGE_USAGE_QUERY', 'analytics.forecast.queries.STORAGE_CAPACITY_QUERY'),
        'Observed PVC usage and observed mounted-volume capacity queries execute successfully before range-history validation.',
        allow_empty=True,
    ),
    FeatureContract(
        'top.cpu',
        'Top Consumers',
        'Top CPU Consumers Contract',
        ('analytics.top_consumers.queries.TOP_CPU_CONSUMERS_QUERY',),
        'The exact top CPU consumer query executes successfully. Empty is valid when no eligible workload is observed.',
        allow_empty=True,
    ),
    FeatureContract(
        'top.memory',
        'Top Consumers',
        'Top Memory Consumers Contract',
        ('analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_QUERY',),
        'The exact top memory consumer query executes successfully. Empty is valid when no eligible workload is observed.',
        allow_empty=True,
    ),
    FeatureContract(
        'alerts.active',
        'Alerts & Anomalies',
        'Active Alerts Contract',
        ('analytics.alerts.queries.PROMETHEUS_ALERTS_QUERY',),
        'The exact active-alert query executes successfully. Empty means no alert is currently observed.',
        allow_empty=True,
    ),
    FeatureContract(
        'alerts.anomaly',
        'Alerts & Anomalies',
        'Pod Restart Anomaly Contract',
        ('analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY',),
        'The exact anomaly query executes successfully. Empty means no anomaly is currently observed.',
        allow_empty=True,
    ),
)


def evaluate_feature_contracts(client: Any, *, sample_namespace: str = 'default') -> list[dict[str, Any]]:
    return [_evaluate(client, contract, sample_namespace=sample_namespace) for contract in FEATURE_CONTRACTS]


def _evaluate(client: Any, contract: FeatureContract, *, sample_namespace: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    successful = 0
    usable = 0
    observed_labels: set[str] = set()
    query_texts: list[str] = []

    for query_key in contract.query_keys:
        definition = get_query(query_key)
        registered_expression = definition.expression.replace('$namespace', _escape_label_value(sample_namespace))
        expression = _validation_expression(contract, registered_expression)
        query_texts.append(expression)
        try:
            response = client.query(expression)
        except PrometheusError as exc:
            checks.append(
                _check(
                    query_key,
                    'failed',
                    f'Endpoint rejected the validation query: {exc}',
                    expression,
                    0,
                    None,
                    error_detail=str(exc),
                    registered_query=registered_expression,
                )
            )
            continue
        except Exception as exc:  # unexpected evaluator faults are isolated per query
            checks.append(
                _check(
                    query_key,
                    'failed',
                    f'Query evaluation raised {type(exc).__name__}: {exc}',
                    expression,
                    0,
                    None,
                    error_detail=f'{type(exc).__name__}: {exc}',
                    registered_query=registered_expression,
                )
            )
            continue

        if response.get('status') != 'success':
            detail = _response_error_detail(response)
            checks.append(
                _check(
                    query_key,
                    'failed',
                    f'Endpoint rejected the exact registered query: {detail}',
                    expression,
                    0,
                    None,
                    error_detail=detail,
                    registered_query=registered_expression,
                )
            )
            continue

        successful += 1
        rows = response.get('data', {}).get('result', []) or []
        row_usable, labels, value_summary = _usable_rows(rows)
        identity_keys = _filesystem_identity_keys(rows) if contract.key == 'storage.filesystem' else ()
        usable += row_usable
        observed_labels.update(labels)
        status = 'ready' if row_usable else ('not_observed' if contract.allow_empty else 'failed')
        evidence = value_summary or 'Query returned no usable samples.'
        checks.append(
            _check(
                query_key,
                status,
                evidence,
                expression,
                len(rows),
                value_summary,
                registered_query=registered_expression,
                identity_keys=identity_keys,
            )
        )

    label_ready = _required_labels_satisfied(contract.required_labels, observed_labels)
    if contract.key == 'storage.filesystem':
        # /var is preferred; root is fallback. A complete size+available pair plus
        # canonical node identity is required. A size metric alone proves capacity
        # collection but cannot support filesystem utilization or headroom.
        var_pairs = _matching_identity_pairs(checks[0], checks[1])
        root_pairs = _matching_identity_pairs(checks[2], checks[3])
        var_ready = bool(var_pairs)
        root_ready = bool(root_pairs)
        status = 'ready' if var_ready or root_ready else 'failed'
        label_ready = bool(var_pairs or root_pairs)
        pair_evidence = (
            f'/var size {_check_state(checks[0])}; /var available {_check_state(checks[1])}; '
            f'matching /var pairs {len(var_pairs)}; / size {_check_state(checks[2])}; '
            f'/ available {_check_state(checks[3])}; matching / pairs {len(root_pairs)}; '
            f'canonical node identity {"Ready" if label_ready else "Missing"}.'
        )
        observed = (
            f'{pair_evidence} {successful} of {len(contract.query_keys)} queries executed; '
            f'{usable} usable filesystem samples; observed labels: '
            f'{", ".join(sorted(observed_labels)) or "none"}.'
        )
    elif successful != len(contract.query_keys):
        status = 'failed'
        observed = f'{successful} of {len(contract.query_keys)} registered analytics queries executed successfully.'
    elif usable:
        status = 'ready'
        observed = f'{usable} usable samples returned by the registered analytics query contract.'
    elif contract.allow_empty:
        status = 'not_observed'
        observed = 'All registered queries executed successfully but returned no currently observable series.'
    else:
        status = 'failed'
        observed = 'Registered queries executed but returned no usable samples.'

    status_label = {'ready': 'Ready', 'failed': 'Failed', 'not_observed': 'Not Observed'}[status]
    remediation = (
        _storage_remediation(checks, label_ready)
        if contract.key == 'storage.filesystem' and status != 'ready'
        else _remediation(status, successful, len(contract.query_keys), usable)
    )
    return {
        'key': contract.key,
        'feature': contract.feature,
        'label': contract.label,
        'status': status,
        'status_label': status_label,
        'expected': contract.expected,
        'observed': observed,
        'query_count_display': f'{len(contract.query_keys)} registered queries',
        'technical_check_count_display': f'{len(checks)} technical checks',
        'technical_checks': checks,
        'validation_queries': query_texts,
        'observed_labels_display': ', '.join(sorted(observed_labels)) or 'No labels observed',
        'recommendation': remediation,
    }


def _validation_expression(contract: FeatureContract, expression: str) -> str:
    if contract.key != 'storage.filesystem':
        return expression
    # Validation only needs identity and presence evidence. Aggregating the raw
    # node_exporter vectors prevents a large multi-cluster endpoint from returning
    # thousands of label-heavy samples while preserving the labels required to
    # prove a usable size/available pair.
    return f'count by (node, nodename, kubernetes_node, mountpoint) ({expression})'


def _filesystem_identity_keys(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    identities: set[str] = set()
    for row in rows:
        labels = row.get('metric') or {}
        node = next(
            (str(labels.get(name)) for name in ('node', 'nodename', 'kubernetes_node') if labels.get(name)),
            '',
        )
        mountpoint = str(labels.get('mountpoint') or '')
        if node and mountpoint:
            identities.add(f'{node}::{mountpoint}')
    return tuple(sorted(identities))


def _matching_identity_pairs(left: dict[str, Any], right: dict[str, Any]) -> set[str]:
    left_identities: set[str] = set()
    right_identities: set[str] = set()

    for item in left.get('identity_keys') or ():
        if item:
            left_identities.add(str(item))

    for item in right.get('identity_keys') or ():
        if item:
            right_identities.add(str(item))

    return left_identities & right_identities


def _check_state(check: dict[str, Any]) -> str:
    if check.get('status') == 'ready':
        return f'Ready ({check.get("series_count_display")})'
    if check.get('error_detail'):
        return f'Failed ({check.get("error_detail")})'
    return 'No Data'


def _storage_remediation(checks: list[dict[str, Any]], label_ready: bool) -> str:
    var_missing = [
        label
        for label, check in zip(('/var size', '/var available'), checks[:2], strict=False)
        if check.get('status') != 'ready'
    ]
    root_missing = [
        label
        for label, check in zip(('/ size', '/ available'), checks[2:4], strict=False)
        if check.get('status') != 'ready'
    ]
    options = []
    if var_missing:
        options.append(f'complete the preferred /var pair by verifying {", ".join(var_missing)}')
    if root_missing:
        options.append(f'or complete the fallback / pair by verifying {", ".join(root_missing)}')
    if not options:
        options.append('align size and available series on the same canonical node identity and mountpoint')
    identity = (
        ' Also expose a canonical node identity label (node, nodename, or kubernetes_node).' if not label_ready else ''
    )
    return (
        f'KAORI observed only part of the filesystem contract: {"; ".join(options)}.'
        f'{identity} Storage readiness requires both node_filesystem_size_bytes and '
        'node_filesystem_avail_bytes for one complete mount pair using the same scope selector.'
    )


def _usable_rows(rows: list[dict[str, Any]]) -> tuple[int, set[str], str | None]:
    usable = 0
    labels: set[str] = set()
    values: list[float] = []
    for row in rows:
        metric = row.get('metric') or {}
        labels.update(metric.keys())
        raw = (row.get('value') or [None, None])[1]
        if raw is None:
            continue
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            continue
        if not isfinite(numeric):
            continue
        usable += 1
        values.append(numeric)
    if not values:
        return usable, labels, None
    if len(values) == 1:
        value = values[0]
        rendered = str(int(value)) if value.is_integer() else f'{value:.4g}'
        return (
            usable,
            labels,
            f'One numeric sample returned with value {rendered}. Empty metric labels are valid for aggregate queries.',
        )
    return usable, labels, f'{len(values)} numeric samples returned.'


def _required_labels_satisfied(requirements: tuple[str, ...], observed: set[str]) -> bool:
    for requirement in requirements:
        alternatives = requirement.split('|')
        if not any(item in observed for item in alternatives):
            return False
    return True


def _check(
    key: str,
    status: str,
    evidence: str,
    query: str,
    series_count: int,
    value_summary: str | None,
    *,
    error_detail: str | None = None,
    registered_query: str | None = None,
    identity_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        'key': key,
        'label': key.rsplit('.', 1)[-1].replace('_', ' ').title(),
        'status': status,
        'status_label': {'ready': 'Ready', 'failed': 'Failed', 'not_observed': 'Not Observed'}[status],
        'evidence': evidence,
        'query': query,
        'registered_query': registered_query or query,
        'identity_keys': list(identity_keys),
        'matching_identity_count': len(identity_keys),
        'series_count_display': f'{series_count} response series',
        'value_summary': value_summary or 'No numeric sample observed',
        'error_detail': error_detail,
    }


def _response_error_detail(response: dict[str, Any]) -> str:
    error_type = str(response.get('errorType') or '').strip()
    error = str(response.get('error') or '').strip()
    detail = ': '.join(part for part in (error_type, error) if part)
    return detail or 'endpoint returned a non-success response'


def _remediation(status: str, successful: int, expected: int, usable: int) -> str:
    if status == 'ready':
        return 'No remediation is required. The exact registered Analytics query contract passed.'
    if status == 'not_observed':
        return 'No configuration change is required solely from this result. Confirm whether the cluster currently has eligible objects or active signals.'
    if successful < expected:
        return 'Run the displayed query against the configured Prometheus or Thanos endpoint, then review endpoint routing, query profile compatibility, and proxy/API errors.'
    if not usable:
        return 'The query was accepted but returned no usable sample. Review selectors, recording rules, relabeling, cluster labels, and current object availability.'
    return 'Review the displayed expected and observed evidence before changing exporters or metrics pipelines.'


def _escape_label_value(value: str) -> str:
    return str(value).replace('\\', '\\\\').replace('"', '\\"')
