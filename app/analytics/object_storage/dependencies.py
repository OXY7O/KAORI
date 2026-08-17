from __future__ import annotations

from typing import Literal, TypedDict

from app.analytics.shared.metrics import MetricReadinessState, MetricsSourceError, MetricsSourceFailureKind
from app.models.object_storage import ObjectStorageSystem

ObjectStorageDependencyKind = Literal[
    'system_required',
    'inventory_required',
    'metrics_source_setup',
    'metrics_source_validation',
    'metrics_source_capability',
    'metrics_source_connection',
    'metrics_source_authentication',
    'metrics_source_query',
]


class ObjectStorageDependencyBlocker(TypedDict):
    kind: ObjectStorageDependencyKind
    stage: int
    badge: str
    tone: str
    title: str
    description: str
    diagnostic_detail: str | None
    icon: str
    action_label: str
    action_endpoint: str


def system_required_blocker() -> ObjectStorageDependencyBlocker:
    return {
        'kind': 'system_required',
        'stage': 1,
        'badge': 'Storage Setup Required',
        'tone': 'warning',
        'title': 'Object Storage Setup Required',
        'description': (
            'Register and validate a Storage integration, then run Object Storage Inventory Sync before opening operational analytics.'
        ),
        'diagnostic_detail': None,
        'icon': 'database-zap',
        'action_label': 'Open Storage Integrations',
        'action_endpoint': 'integrations.storage',
    }


def inventory_required_blocker(system: ObjectStorageSystem) -> ObjectStorageDependencyBlocker:
    return {
        'kind': 'inventory_required',
        'stage': 1,
        'badge': 'Inventory Sync Required',
        'tone': 'warning',
        'title': 'Object Storage Inventory Sync Required',
        'description': (
            f'{system.name} is registered, but no committed Object Storage inventory snapshot is available. '
            'Run Object Storage Inventory Sync before loading operational analytics.'
        ),
        'diagnostic_detail': None,
        'icon': 'database-clock',
        'action_label': 'Open Object Storage Inventory',
        'action_endpoint': 'object_storage_inventory.overview',
    }


def metrics_source_setup_blocker(
    system: ObjectStorageSystem,
    *,
    detail: str,
) -> ObjectStorageDependencyBlocker:
    return {
        'kind': 'metrics_source_setup',
        'stage': 2,
        'badge': 'Metrics Source Required',
        'tone': 'warning',
        'title': 'Operational Metrics Source Required',
        'description': (
            f'No supported operational metrics source is ready for {system.name}. '
            'Bind and validate a metrics provider before loading Object Storage Analytics.'
        ),
        'diagnostic_detail': detail,
        'icon': 'activity',
        'action_label': 'Open Observability Integrations',
        'action_endpoint': 'integrations.observability',
    }


def metrics_validation_blocker(
    system: ObjectStorageSystem,
    *,
    status: MetricReadinessState,
    status_label: str,
    detail: str,
) -> ObjectStorageDependencyBlocker:
    if status == MetricReadinessState.NOT_VALIDATED:
        stale = 'stale' in detail.lower()
        badge = 'Consumer Validation Stale' if stale else 'Consumer Validation Required'
        title = (
            'Object Storage Metrics Binding Must Be Revalidated'
            if stale
            else 'Object Storage Metrics Binding Requires Validation'
        )
        icon = 'list-checks'
    else:
        badge = status_label
        title = 'Required Metrics Contract Incomplete'
        icon = 'shield-alert'
    return {
        'kind': 'metrics_source_validation'
        if status == MetricReadinessState.NOT_VALIDATED
        else 'metrics_source_capability',
        'stage': 2,
        'badge': badge,
        'tone': 'warning',
        'title': title,
        'description': (
            f'{system.name} has a bound metrics source, but its Object Storage consumer binding is not eligible yet. '
            'Run Metrics Source Full Validation or Validate on the consumer binding, then resolve any required metric-family, label, or query gaps.'
        ),
        'diagnostic_detail': detail,
        'icon': icon,
        'action_label': 'Review Metrics Binding',
        'action_endpoint': 'integrations.observability',
    }


def metrics_runtime_blocker(
    system: ObjectStorageSystem,
    exc: MetricsSourceError,
) -> ObjectStorageDependencyBlocker:
    if exc.kind == MetricsSourceFailureKind.AUTHENTICATION:
        return {
            'kind': 'metrics_source_authentication',
            'stage': 2,
            'badge': 'Authentication Failed',
            'tone': 'critical',
            'title': 'Operational Metrics Authentication Failed',
            'description': (
                f'The bound metrics source for {system.name} rejected KAORI runtime access. '
                'Review credentials and provider authentication before continuing.'
            ),
            'diagnostic_detail': str(exc),
            'icon': 'shield-x',
            'action_label': 'Review Observability Integrations',
            'action_endpoint': 'integrations.observability',
        }
    return {
        'kind': 'metrics_source_connection',
        'stage': 2,
        'badge': 'Disconnected',
        'tone': 'critical',
        'title': 'Operational Metrics Source Disconnected',
        'description': (
            f'The metrics source bound to {system.name} is currently unreachable. '
            'Committed Inventory remains available, but live Object Storage Analytics is blocked until runtime connectivity is restored.'
        ),
        'diagnostic_detail': str(exc),
        'icon': 'plug-zap',
        'action_label': 'Review Observability Integrations',
        'action_endpoint': 'integrations.observability',
    }


def metrics_query_blocker(
    system: ObjectStorageSystem,
    *,
    detail: str,
) -> ObjectStorageDependencyBlocker:
    return {
        'kind': 'metrics_source_query',
        'stage': 2,
        'badge': 'Runtime Query Failed',
        'tone': 'critical',
        'title': 'Operational Metrics Query Failed',
        'description': (
            f'The metrics source for {system.name} is reachable, but KAORI could not complete any '
            'runtime metric query for this analysis. Review the validated query profile and provider response before continuing.'
        ),
        'diagnostic_detail': detail,
        'icon': 'file-warning',
        'action_label': 'Review Observability Integrations',
        'action_endpoint': 'integrations.observability',
    }


def resolver_error_blocker(
    system: ObjectStorageSystem,
    exc: MetricsSourceError,
) -> ObjectStorageDependencyBlocker:
    if exc.kind in {MetricsSourceFailureKind.TRANSPORT, MetricsSourceFailureKind.AUTHENTICATION}:
        return metrics_runtime_blocker(system, exc)
    if exc.provider:
        return {
            'kind': 'metrics_source_capability',
            'stage': 2,
            'badge': 'Capability Incomplete',
            'tone': 'warning',
            'title': 'Metrics Provider Profile Not Supported',
            'description': (
                f'A metrics provider is bound to {system.name}, but KAORI does not have a qualified '
                'Object Storage metric profile for this asset/provider combination.'
            ),
            'diagnostic_detail': str(exc),
            'icon': 'shield-alert',
            'action_label': 'Review Observability Integrations',
            'action_endpoint': 'integrations.observability',
        }
    return metrics_source_setup_blocker(system, detail=str(exc))
