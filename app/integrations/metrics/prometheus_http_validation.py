from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.integrations.metrics.capabilities import PROVIDER_CAPABILITY_KEYS, definition
from app.integrations.metrics.exceptions import MetricsSourceError
from app.integrations.metrics.prometheus_http_client import PrometheusHttpQueryClient

PROFILE_KEY = 'prometheus-http-core-v1'
PROFILE_VERSION = 1


_PROBE_EXPRESSIONS = {
    'instant_query': 'vector(1)',
    'range_query': 'vector(1)',
    'series_discovery': 'up',
    'label_discovery': '__name__',
}


def validate_metrics_core(client: PrometheusHttpQueryClient) -> dict[str, Any]:
    """Validate only provider-level Prometheus HTTP/API capabilities.

    Consumer metrics (Kubernetes, MinIO, and future integrations) are deliberately
    excluded. They are validated through asset-scoped IntegrationBinding profiles.
    """

    now = datetime.now(UTC)
    start = now - timedelta(minutes=5)
    checks: tuple[tuple[str, Callable[[], dict[str, Any]], str], ...] = (
        (
            'instant_query',
            lambda: client.query('vector(1)'),
            'The instant query endpoint accepted a provider-neutral PromQL probe.',
        ),
        (
            'range_query',
            lambda: client.query_range(
                'vector(1)',
                str(start.timestamp()),
                str(now.timestamp()),
                '60',
            ),
            'The range query endpoint accepted a provider-neutral PromQL probe.',
        ),
        (
            'series_discovery',
            lambda: client.series(['up'], limit=1),
            'The series discovery endpoint responded successfully.',
        ),
        (
            'label_discovery',
            lambda: client.label_values('__name__'),
            'The label discovery endpoint responded successfully.',
        ),
    )

    assessments: list[dict[str, Any]] = []
    available: list[str] = []
    for key, probe, success_evidence in checks:
        capability = definition(key)
        try:
            payload = probe()
            success = isinstance(payload, dict) and payload.get('status') == 'success'
            detail = (
                success_evidence
                if success
                else str((payload or {}).get('error') or 'Prometheus returned an unsuccessful API response.')
            )
        except (MetricsSourceError, AttributeError, TypeError, ValueError) as exc:
            success = False
            detail = f'{type(exc).__name__}: {exc}'

        status = 'available' if success else 'missing'
        if success:
            available.append(key)
        assessments.append(
            {
                'key': key,
                'label': capability.label if capability else key.replace('_', ' ').title(),
                'status': status,
                'evidence': detail,
                'impact': capability.impact if capability else '',
                'recommendation': capability.recommendation if capability else '',
                'source_owner': capability.source_owner if capability else 'Configured metrics query adapter',
                'required_by': list(capability.required_by) if capability else [],
                'expected_signals': list(capability.expected_signals) if capability else [],
                'validation_query': _PROBE_EXPRESSIONS.get(key),
                'technical_checks': [
                    {
                        'label': capability.label if capability else key.replace('_', ' ').title(),
                        'status': status,
                        'evidence': detail,
                    }
                ],
            }
        )

    missing = [key for key in PROVIDER_CAPABILITY_KEYS if key not in available]
    status = 'ready' if not missing else 'blocked'
    return {
        'profile': PROFILE_KEY,
        'profile_version': PROFILE_VERSION,
        'checked_at': now.isoformat(),
        'status': status,
        'available_capabilities': available,
        'missing_capabilities': missing,
        'capability_assessments': assessments,
        'summary': {
            'status': status,
            'total_count': len(PROVIDER_CAPABILITY_KEYS),
            'ready_count': len(available),
            'failed_count': len(missing),
        },
    }
