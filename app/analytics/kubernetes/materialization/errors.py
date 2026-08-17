from __future__ import annotations

from dataclasses import dataclass

from billiard.exceptions import SoftTimeLimitExceeded

from app.integrations.metrics.exceptions import (
    MetricsQueryError,
    MetricsSourceAuthenticationError,
    MetricsSourceConnectionError,
    MetricsSourceError,
)


class AnalyticsDatasetTimeoutError(TimeoutError):
    """Raised when one analytics dataset exceeds its isolated worker budget."""


class AnalyticsSourceBusyError(TimeoutError):
    """Raised when a shared provider query slot cannot be acquired in time."""


class AnalyticsDependencyError(RuntimeError):
    """Raised when a builder reports an unavailable source or capability."""


@dataclass(frozen=True, slots=True)
class AnalyticsFailure:
    code: str
    title: str
    detail: str
    remediation: str
    retryable: bool

    def log_message(self) -> str:
        return f'[{self.code}] {self.title}: {self.detail} Recommended action: {self.remediation}'


def _is_timeout_message(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            'timeout',
            'timed out',
            'deadline exceeded',
            'context deadline',
            'connection timeout',
            'read timed out',
        )
    )


def classify_analytics_failure(
    error: Exception | str,
    *,
    dataset_label: str,
    cluster_name: str,
) -> AnalyticsFailure:
    if isinstance(error, Exception):
        message = str(error).strip() or error.__class__.__name__
    else:
        message = str(error).strip() or 'Unknown analytics materialization error'
    context = f'{dataset_label} for {cluster_name}'

    if isinstance(error, (AnalyticsDatasetTimeoutError, SoftTimeLimitExceeded)):
        return AnalyticsFailure(
            code='dataset_timeout',
            title='Analytics dataset exceeded its worker time limit',
            detail=f'{context} did not finish before the configured dataset or task deadline. {message}',
            remediation=(
                'Reduce precomputed long ranges, increase Metrics Source query capacity, '
                'or raise the analytics dataset and task time limits after capacity review.'
            ),
            retryable=True,
        )
    if isinstance(error, AnalyticsDependencyError):
        lowered = message.lower()
        if _is_timeout_message(message):
            return AnalyticsFailure(
                code='provider_timeout',
                title='Analytics source timed out during materialization',
                detail=f'{context} reported an unavailable dependency. {message}',
                remediation=(
                    'Review Metrics Source query saturation and worker logs, then retry. '
                    'The last successful snapshot remains available within its stale window.'
                ),
                retryable=True,
            )
        if any(code in lowered for code in ('http 429', 'http 500', 'http 502', 'http 503', 'http 504')):
            return AnalyticsFailure(
                code='provider_overloaded',
                title='Analytics source was overloaded or temporarily unavailable',
                detail=f'{context} reported an unavailable dependency. {message}',
                remediation=(
                    'Review provider CPU, memory, query concurrency, and slow-query logs. '
                    'Retry after the current analytics workload finishes.'
                ),
                retryable=True,
            )
        return AnalyticsFailure(
            code='analytics_dependency_unavailable',
            title='Analytics source or capability is unavailable',
            detail=f'{context} could not satisfy its source dependency. {message}',
            remediation=(
                'Review Integrations readiness, cluster binding scope, and the worker log '
                'for the exact missing source or capability.'
            ),
            retryable=True,
        )
    if isinstance(error, AnalyticsSourceBusyError):
        return AnalyticsFailure(
            code='source_busy',
            title='Analytics source query slot was busy',
            detail=f'{context} waited for another query workload using the same provider. {message}',
            remediation='Allow the active analytics execution to finish, then retry this dataset.',
            retryable=True,
        )
    if isinstance(error, MetricsSourceAuthenticationError):
        return AnalyticsFailure(
            code='provider_authentication_failed',
            title='Metrics Source authentication failed',
            detail=f'{context} was rejected by the configured metrics endpoint. {message}',
            remediation='Verify the bearer token/basic credentials and rerun integration validation.',
            retryable=False,
        )
    if isinstance(error, MetricsSourceConnectionError):
        if _is_timeout_message(message):
            return AnalyticsFailure(
                code='provider_timeout',
                title='Metrics Source did not respond before the query timeout',
                detail=f'{context} could not complete a metrics request. {message}',
                remediation=(
                    'Review Metrics Source CPU, memory, query concurrency, and slow-query logs. '
                    'Reduce long precomputed ranges or increase the analytics range-query timeout.'
                ),
                retryable=True,
            )
        return AnalyticsFailure(
            code='provider_connection_failed',
            title='Metrics Source connection failed',
            detail=f'{context} could not reach the configured metrics endpoint. {message}',
            remediation='Verify endpoint routing, DNS, TLS, authentication, and provider availability.',
            retryable=True,
        )
    if isinstance(error, MetricsQueryError):
        lowered = message.lower()
        if any(code in lowered for code in ('http 429', 'http 500', 'http 502', 'http 503', 'http 504')):
            return AnalyticsFailure(
                code='provider_overloaded',
                title='Metrics Source rejected or could not complete a heavy query',
                detail=f'{context} received a transient provider response. {message}',
                remediation=(
                    'Review Metrics Source query limits and resource saturation, then retry. '
                    'Keep analytics source concurrency limited and precompute only required ranges.'
                ),
                retryable=True,
            )
        return AnalyticsFailure(
            code='promql_query_failed',
            title='Metrics Source rejected an analytics query',
            detail=f'{context} returned a metrics-query execution error. {message}',
            remediation='Review worker logs for the query fingerprint and validate metric/label compatibility.',
            retryable=False,
        )
    if isinstance(error, MetricsSourceError):
        return AnalyticsFailure(
            code='provider_runtime_failed',
            title='Metrics Source analytics runtime failed',
            detail=f'{context} could not use the selected metrics source. {message}',
            remediation='Review Integration Runtime, binding validation, and analytics worker logs.',
            retryable=True,
        )
    if isinstance(error, LookupError):
        return AnalyticsFailure(
            code='analytics_configuration_error',
            title='Analytics dataset configuration is invalid',
            detail=f'{context} could not resolve its registered dataset or source contract. {message}',
            remediation='Review the analytics dataset registry and job configuration.',
            retryable=False,
        )
    return AnalyticsFailure(
        code='analytics_materialization_failed',
        title='Analytics materialization failed',
        detail=f'{context} did not produce a usable snapshot. {message}',
        remediation='Review the worker traceback and the failed snapshot details before retrying.',
        retryable=False,
    )
