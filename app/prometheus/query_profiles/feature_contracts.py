from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from app.prometheus.query_profiles import get_query


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
    FeatureContract('capacity.cpu', 'Capacity Analytics', 'CPU Capacity Contract', ('analytics.utilization.queries.CPU_CAPACITY',), 'The analytics query returns a positive numeric CPU capacity value.'),
    FeatureContract('capacity.memory', 'Capacity Analytics', 'Memory Capacity Contract', ('analytics.utilization.queries.MEMORY_CAPACITY',), 'The analytics query returns a positive numeric memory capacity value.'),
    FeatureContract('capacity.worker', 'Capacity Analytics', 'Worker Capacity Contract', ('analytics.capacity.queries.CURRENT_WORKER_PODS_QUERY', 'analytics.capacity.queries.WORKER_CPU_USAGE_QUERY'), 'The worker discovery and worker usage queries execute successfully and return usable values.'),
    FeatureContract('utilization.cpu', 'Utilization Analytics', 'CPU Utilization Contract', ('analytics.utilization.queries.CPU_UTILIZATION',), 'The exact CPU utilization query executes successfully and returns a numeric value.'),
    FeatureContract('utilization.memory', 'Utilization Analytics', 'Memory Utilization Contract', ('analytics.utilization.queries.MEMORY_UTILIZATION',), 'The exact memory utilization query executes successfully and returns a numeric value.'),
    FeatureContract('utilization.storage', 'Utilization Analytics', 'Storage Utilization Contract', ('analytics.utilization.queries.STORAGE_UTILIZATION',), 'The exact storage utilization query executes successfully and returns a numeric value.', allow_empty=True),
    FeatureContract('storage.filesystem', 'Storage Analytics', 'Storage Filesystem Contract', ('analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY', 'analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY', 'analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY', 'analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY'), 'Either the /var pair or the / pair returns usable filesystem series with canonical node identity.', required_labels=('node|nodename|kubernetes_node',)),
    FeatureContract('storage.pvc', 'Storage Analytics', 'PVC Usage Contract', ('analytics.storage.queries.PVC_USED_BY_CLAIM_QUERY', 'analytics.storage.queries.PVC_AVAILABLE_BY_CLAIM_QUERY'), 'PVC usage queries execute successfully. An empty result is valid when no active PVC is observed.', allow_empty=True),
    FeatureContract('workload.namespace', 'Workload Analytics', 'Namespace Contract', ('analytics.workload.queries.NAMESPACE_ACTIVE_QUERY',), 'The namespace query executes successfully and returns observable namespaces.', allow_empty=True),
    FeatureContract('workload.owner', 'Workload Analytics', 'Workload Owner Mapping Contract', ('analytics.workload.queries.WORKLOAD_POD_OWNER_QUERY',), 'The exact workload owner query executes successfully. Empty is reported as Not Observed, not Missing.', allow_empty=True),
    FeatureContract('workload.qos', 'Workload Analytics', 'Workload QoS Contract', ('analytics.workload.queries.WORKLOAD_QOS_QUERY',), 'The exact QoS query executes successfully. Empty is reported as Not Observed.', allow_empty=True),
    FeatureContract('workload.resources', 'Workload Analytics', 'Requests and Limits Contract', ('analytics.workload.queries.WORKLOAD_CPU_REQUESTS_QUERY', 'analytics.workload.queries.WORKLOAD_CPU_LIMITS_QUERY'), 'The exact workload request and limit queries execute successfully.', allow_empty=True),
    FeatureContract('forecast.cpu', 'Forecast Analytics', 'CPU Forecast Input Contract', ('analytics.forecast.queries.CPU_USAGE_QUERY', 'analytics.forecast.queries.CPU_WORKER_CAPACITY_QUERY'), 'Current CPU usage and capacity queries execute successfully before range-history validation.'),
    FeatureContract('forecast.memory', 'Forecast Analytics', 'Memory Forecast Input Contract', ('analytics.forecast.queries.MEMORY_USAGE_QUERY', 'analytics.forecast.queries.MEMORY_WORKER_CAPACITY_QUERY'), 'Current memory usage and capacity queries execute successfully before range-history validation.'),
    FeatureContract('top.cpu', 'Top Consumers', 'Top CPU Consumers Contract', ('analytics.top_consumers.queries.TOP_CPU_CONSUMERS_QUERY',), 'The exact top CPU consumer query executes successfully. Empty is valid when no eligible workload is observed.', allow_empty=True),
    FeatureContract('top.memory', 'Top Consumers', 'Top Memory Consumers Contract', ('analytics.top_consumers.queries.TOP_MEMORY_CONSUMERS_QUERY',), 'The exact top memory consumer query executes successfully. Empty is valid when no eligible workload is observed.', allow_empty=True),
    FeatureContract('alerts.active', 'Alerts & Anomalies', 'Active Alerts Contract', ('analytics.alerts.queries.PROMETHEUS_ALERTS_QUERY',), 'The exact active-alert query executes successfully. Empty means no alert is currently observed.', allow_empty=True),
    FeatureContract('alerts.anomaly', 'Alerts & Anomalies', 'Pod Restart Anomaly Contract', ('analytics.alerts.queries.POD_RESTART_ANOMALY_QUERY',), 'The exact anomaly query executes successfully. Empty means no anomaly is currently observed.', allow_empty=True),
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
        expression = definition.expression.replace('$namespace', _escape_label_value(sample_namespace))
        query_texts.append(expression)
        try:
            response = client.query(expression)
        except Exception as exc:  # endpoint errors are evidence, not template assumptions
            checks.append(_check(query_key, 'failed', f'Query execution raised {type(exc).__name__}: {exc}', expression, 0, None))
            continue

        if response.get('status') != 'success':
            checks.append(_check(query_key, 'failed', 'Prometheus-compatible endpoint rejected the query.', expression, 0, None))
            continue

        successful += 1
        rows = response.get('data', {}).get('result', []) or []
        row_usable, labels, value_summary = _usable_rows(rows)
        usable += row_usable
        observed_labels.update(labels)
        status = 'ready' if row_usable else ('not_observed' if contract.allow_empty else 'failed')
        evidence = value_summary if row_usable else 'Query returned no usable samples.'
        checks.append(_check(query_key, status, evidence, expression, len(rows), value_summary))

    label_ready = _required_labels_satisfied(contract.required_labels, observed_labels)
    if successful != len(contract.query_keys):
        status = 'failed'
        observed = f'{successful} of {len(contract.query_keys)} registered analytics queries executed successfully.'
    elif contract.key == 'storage.filesystem':
        # /var is preferred; root is fallback. One complete pair plus canonical identity is sufficient.
        var_ready = all(checks[i]['status'] == 'ready' for i in (0, 1))
        root_ready = all(checks[i]['status'] == 'ready' for i in (2, 3))
        if (var_ready or root_ready) and label_ready:
            status = 'ready'
        elif not usable:
            status = 'failed'
        else:
            status = 'failed'
        observed = f'{usable} usable filesystem samples; observed labels: {", ".join(sorted(observed_labels)) or "none"}.'
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
    remediation = _remediation(status, successful, len(contract.query_keys), usable)
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


def _usable_rows(rows: list[dict[str, Any]]) -> tuple[int, set[str], str | None]:
    usable = 0
    labels: set[str] = set()
    values: list[float] = []
    for row in rows:
        metric = row.get('metric') or {}
        labels.update(metric.keys())
        raw = (row.get('value') or [None, None])[1]
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
        return usable, labels, f'One numeric sample returned with value {rendered}. Empty metric labels are valid for aggregate queries.'
    return usable, labels, f'{len(values)} numeric samples returned.'


def _required_labels_satisfied(requirements: tuple[str, ...], observed: set[str]) -> bool:
    for requirement in requirements:
        alternatives = requirement.split('|')
        if not any(item in observed for item in alternatives):
            return False
    return True


def _check(key: str, status: str, evidence: str, query: str, series_count: int, value_summary: str | None) -> dict[str, Any]:
    return {
        'key': key,
        'label': key.rsplit('.', 1)[-1].replace('_', ' ').title(),
        'status': status,
        'status_label': {'ready': 'Ready', 'failed': 'Failed', 'not_observed': 'Not Observed'}[status],
        'evidence': evidence,
        'query': query,
        'series_count_display': f'{series_count} response series',
        'value_summary': value_summary or 'No numeric sample observed',
    }


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
