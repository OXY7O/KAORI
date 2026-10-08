from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.integrations.observability.metrics_source.exceptions import MetricsSourceError
from app.integrations.observability.metrics_source.query_profiles.registry_harbor_v1 import (
    PROFILE_KEY,
    PROFILE_LABEL,
    list_registry_queries,
)


def _observed_series(series: list[dict[str, Any]]) -> tuple[set[str], dict[str, set[str]], set[str]]:
    observed: set[str] = set()
    labels: dict[str, set[str]] = defaultdict(set)
    versions: set[str] = set()
    for row in series:
        metric = str(row.get('__name__') or '').strip()
        if not metric:
            continue
        observed.add(metric)
        labels[metric].update(str(key) for key in row if key != '__name__')
        if metric == 'harbor_system_info':
            version = str(row.get('harbor_version') or row.get('version') or '').strip().lstrip('v')
            if version:
                versions.add(version)
    return observed, labels, versions


def _missing_contract(
    definition: Any,
    observed: set[str],
    labels: dict[str, set[str]],
) -> tuple[list[str], list[str]]:
    missing_metrics = [metric for metric in definition.required_metrics if metric not in observed]
    missing_labels = [
        f'{metric}.{label}'
        for metric, required in definition.required_labels
        for label in required
        if label not in labels.get(metric, set())
    ]
    return missing_metrics, missing_labels


def _query_status(client: Any, expression: str) -> tuple[str, str]:
    try:
        result = client.query(expression)
    except MetricsSourceError as exc:
        return 'blocked', f'Registered Registry metrics query failed: {exc}'
    values = (result.get('data') or {}).get('result') if isinstance(result, dict) else None
    if not isinstance(values, list) or not values:
        return 'no_data', 'Query executed successfully but returned no scoped samples.'
    return 'ready', 'Scoped metric family and label contract are available.'


def _audit_definition(
    client: Any,
    definition: Any,
    *,
    observed: set[str],
    labels: dict[str, set[str]],
    execute_queries: bool,
) -> dict[str, Any]:
    missing_metrics, missing_labels = _missing_contract(definition, observed, labels)
    status = 'ready'
    detail = 'Scoped metric family and label contract are available.'
    if missing_metrics:
        status = 'blocked' if definition.readiness_tier == 'required' else 'unsupported'
        detail = f'Missing scoped metric family: {", ".join(missing_metrics)}.'
    elif missing_labels:
        status = 'blocked'
        detail = f'Missing required Registry metric label: {", ".join(missing_labels)}.'
    elif execute_queries:
        status, detail = _query_status(client, definition.expression)
    return {
        'key': definition.key,
        'domain': definition.domain,
        'tier': definition.readiness_tier,
        'status': status,
        'detail': detail,
        'required_metrics': list(definition.required_metrics),
        'missing_metrics': missing_metrics,
        'missing_labels': missing_labels,
        'expression': definition.expression,
    }


class RegistryHarborMetricsAuditor:
    """Qualify Harbor metric families through an already-scoped Metrics Source session."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def audit(self, *, execute_queries: bool = True) -> dict[str, Any]:
        definitions = list_registry_queries()
        metrics = sorted({metric for item in definitions for metric in item.required_metrics})
        payload = self.client.series(metrics)
        data = payload.get('data') if isinstance(payload, dict) and payload.get('status') == 'success' else []
        series = [item for item in (data or []) if isinstance(item, dict)]
        observed, labels, versions = _observed_series(series)
        items = [
            _audit_definition(
                self.client,
                definition,
                observed=observed,
                labels=labels,
                execute_queries=execute_queries,
            )
            for definition in definitions
        ]

        required = [item for item in items if item['tier'] == 'required']
        blocked = sum(item['status'] == 'blocked' for item in required)
        no_data = sum(item['status'] == 'no_data' for item in required)
        status = 'ready' if not blocked and not no_data else 'partial'
        return {
            'profile': PROFILE_KEY,
            'profile_label': PROFILE_LABEL,
            'checked_at': datetime.now(UTC).isoformat(),
            'status': status,
            'observed_metrics': sorted(observed),
            'observed_harbor_versions': sorted(versions),
            'summary': {
                'total': len(items),
                'ready': sum(item['status'] == 'ready' for item in items),
                'required_total': len(required),
                'required_ready': sum(item['status'] == 'ready' for item in required),
                'required_blocked': blocked,
                'required_no_data': no_data,
            },
            'items': items,
        }
