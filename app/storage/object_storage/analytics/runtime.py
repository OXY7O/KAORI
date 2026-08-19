from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from app.common.analytics.metrics import (
    MetricPoint,
    MetricReadinessState,
    MetricsReadinessSnapshot,
    MetricsSource,
    MetricsSourceError,
    MetricsSourceFailureKind,
)
from app.models.object_storage import ObjectStorageSystem
from app.storage.object_storage.analytics.dependencies import (
    ObjectStorageDependencyBlocker,
    metrics_query_blocker,
    metrics_runtime_blocker,
    metrics_validation_blocker,
    resolver_error_blocker,
)
from app.storage.object_storage.analytics.sources import resolve_object_storage_metrics_source


class EvidenceReader:
    """Read canonical metrics once per request and fail fast on source-wide failures."""

    def __init__(self, source: MetricsSource) -> None:
        self.source = source
        self.diagnostics: list[str] = []
        self.source_wide_failure: MetricsSourceError | None = None
        self.failed_query_count = 0
        self.successful_query_count = 0
        self.query_states: dict[str, str] = {}

    @property
    def source_label(self) -> str:
        return self.source.identity.provider_label

    def _record_failure(self, exc: MetricsSourceError) -> None:
        self.failed_query_count += 1
        message = str(exc).strip()
        if message:
            self.diagnostics.append(message)
        if exc.source_wide:
            self.source_wide_failure = exc

    def scalar(self, key: str) -> float | None:
        if self.source_wide_failure is not None:
            self.query_states[key] = 'skipped'
            return None
        try:
            value = self.source.scalar(key)
        except MetricsSourceError as exc:
            self._record_failure(exc)
            self.query_states[key] = 'failed'
            return None
        self.successful_query_count += 1
        self.query_states[key] = 'ready' if value is not None else 'no_data'
        return value

    def vector(self, key: str) -> dict[str, float]:
        if self.source_wide_failure is not None:
            self.query_states[key] = 'skipped'
            return {}
        try:
            values = self.source.vector(key, 'bucket')
        except MetricsSourceError as exc:
            self._record_failure(exc)
            self.query_states[key] = 'failed'
            return {}
        self.successful_query_count += 1
        self.query_states[key] = 'ready' if values else 'no_data'
        return values

    def trend(self, key: str, time_range: str) -> list[MetricPoint]:
        if self.source_wide_failure is not None:
            self.query_states[key] = 'skipped'
            return []
        try:
            points = self.source.trend(key, time_range)
        except MetricsSourceError as exc:
            self._record_failure(exc)
            self.query_states[key] = 'failed'
            return []
        self.successful_query_count += 1
        self.query_states[key] = 'ready' if points else 'no_data'
        return points

    def readiness_state(self, key: str) -> str:
        item = next((item for item in self.source.readiness.items if item.key == key), None)
        return item.state.value if item is not None else 'not_validated'

    def evidence_state(self, key: str) -> str:
        runtime_state = self.query_states.get(key)
        if runtime_state in {'failed', 'skipped'}:
            return runtime_state
        if runtime_state == 'ready':
            return 'ready'
        readiness_state = self.readiness_state(key)
        if readiness_state in {'unsupported', 'blocked', 'not_validated'}:
            return readiness_state
        return runtime_state or readiness_state or 'no_data'


def _readiness_status_for_items(items: list[Any]) -> tuple[str, str, str]:
    if not items:
        return 'not_validated', 'Not Validated', 'info'

    required = [item for item in items if item.tier == 'required']
    required_missing = [item for item in required if item.state != MetricReadinessState.READY]
    if required_missing:
        states = {item.state for item in required_missing}
        if MetricReadinessState.BLOCKED in states:
            return 'blocked', 'Blocked', 'critical'
        if MetricReadinessState.NOT_VALIDATED in states:
            return 'not_validated', 'Not Validated', 'info'
        if MetricReadinessState.NO_DATA in states:
            return 'no_data', 'Required No Data', 'warning'
        if MetricReadinessState.UNSUPPORTED in states:
            return 'unsupported', 'Required Unsupported', 'warning'
        return 'partial', 'Required Partial', 'warning'

    if all(item.state == MetricReadinessState.READY for item in items):
        return 'ready', 'Ready', 'normal'
    return 'optional_gaps', 'Optional Gaps', 'info'


def metrics_readiness_view(snapshot: MetricsReadinessSnapshot) -> dict[str, Any]:
    counts = {state.value: snapshot.count(state) for state in MetricReadinessState}
    required_items = [item for item in snapshot.items if item.tier == 'required']
    required_ready_count = sum(item.state == MetricReadinessState.READY for item in required_items)
    required_total_count = len(required_items)
    required_contract_ready = required_total_count > 0 and required_ready_count == required_total_count

    if snapshot.state == MetricReadinessState.NOT_VALIDATED:
        label = (
            'Consumer Validation Stale'
            if snapshot.profile_label == 'Consumer Validation Stale'
            else 'Consumer Validation Required'
        )
        tone = 'warning'
    elif required_contract_ready:
        if counts[MetricReadinessState.READY.value] == snapshot.total_count:
            label, tone = 'Ready', 'normal'
        else:
            label, tone = 'Ready · Optional Gaps', 'info'
    elif snapshot.state == MetricReadinessState.BLOCKED:
        label, tone = 'Contract Blocked', 'critical'
    elif snapshot.state == MetricReadinessState.NO_DATA:
        label, tone = 'Required Metrics No Data', 'warning'
    elif snapshot.state == MetricReadinessState.UNSUPPORTED:
        label, tone = 'Required Metrics Unsupported', 'warning'
    else:
        label, tone = 'Required Metrics Incomplete', 'warning'

    domain_items: dict[str, list[Any]] = defaultdict(list)
    for item in snapshot.items:
        domain_items[item.domain].append(item)
    domains: list[dict[str, Any]] = []
    for domain, items in domain_items.items():
        ready_count = sum(item.state == MetricReadinessState.READY for item in items)
        required = [item for item in items if item.tier == 'required']
        required_ready = sum(item.state == MetricReadinessState.READY for item in required)
        domain_state, status_label, domain_tone = _readiness_status_for_items(items)
        domains.append(
            {
                'label': domain,
                'status': domain_state,
                'status_label': status_label,
                'tone': domain_tone,
                'ready_count': ready_count,
                'total_count': len(items),
                'required_ready_count': required_ready,
                'required_total_count': len(required),
            }
        )

    checked_at: datetime | None = None
    if snapshot.checked_at:
        try:
            checked_at = datetime.fromisoformat(snapshot.checked_at)
        except ValueError:
            checked_at = None
    return {
        'profile': snapshot.profile,
        'profile_label': snapshot.profile_label,
        'status': snapshot.state.value,
        'label': label,
        'tone': tone,
        'checked_at': checked_at,
        'total_count': snapshot.total_count,
        'ready_count': counts[MetricReadinessState.READY.value],
        'partial_count': counts[MetricReadinessState.PARTIAL.value],
        'no_data_count': counts[MetricReadinessState.NO_DATA.value],
        'unsupported_count': counts[MetricReadinessState.UNSUPPORTED.value],
        'blocked_count': counts[MetricReadinessState.BLOCKED.value],
        'not_validated_count': counts[MetricReadinessState.NOT_VALIDATED.value],
        'required_ready_count': required_ready_count,
        'required_total_count': required_total_count,
        'required_contract_ready': required_contract_ready,
        'domains': domains,
        'detail': snapshot.detail,
    }


def waiting_metrics_readiness() -> dict[str, Any]:
    return {
        'profile': 'not-validated',
        'profile_label': 'Operational Metrics Contract',
        'status': 'not_validated',
        'label': 'Consumer Validation Required',
        'tone': 'warning',
        'checked_at': None,
        'total_count': 0,
        'ready_count': 0,
        'partial_count': 0,
        'no_data_count': 0,
        'unsupported_count': 0,
        'blocked_count': 0,
        'not_validated_count': 0,
        'required_ready_count': 0,
        'required_total_count': 0,
        'required_contract_ready': False,
        'domains': [],
        'detail': 'Validate the Object Storage consumer binding before operational analytics is eligible.',
    }


def waiting_metrics_source() -> dict[str, Any]:
    return {
        'configured': False,
        'provider': None,
        'provider_label': 'Metrics Source',
        'instance_name': None,
        'runtime_state': 'waiting',
        'label': 'Waiting for System',
        'tone': 'unknown',
        'detail': 'Select an Object Storage system.',
    }


def source_setup(
    system: ObjectStorageSystem,
) -> tuple[MetricsSource | None, dict[str, Any], dict[str, Any], ObjectStorageDependencyBlocker | None]:
    try:
        source = resolve_object_storage_metrics_source(system)
    except MetricsSourceError as exc:
        blocker = resolver_error_blocker(system, exc)
        if exc.kind == MetricsSourceFailureKind.AUTHENTICATION:
            runtime_state, label, tone = 'authentication_failed', 'Authentication Failed', 'critical'
        elif exc.kind == MetricsSourceFailureKind.TRANSPORT:
            runtime_state, label, tone = 'disconnected', 'Disconnected', 'critical'
        elif exc.provider_key:
            runtime_state, label, tone = 'capability_incomplete', 'Capability Incomplete', 'warning'
        else:
            runtime_state, label, tone = 'not_configured', 'Not Configured', 'warning'
        return (
            None,
            {
                'configured': bool(exc.provider_key),
                'provider_key': exc.provider_key,
                'provider_label': (exc.provider_key.title() if exc.provider_key else 'Metrics Source'),
                'instance_name': None,
                'runtime_state': runtime_state,
                'label': label,
                'tone': tone,
                'detail': str(exc),
            },
            waiting_metrics_readiness(),
            blocker,
        )

    identity = source.identity
    readiness = metrics_readiness_view(source.readiness)
    source_view = {
        'configured': True,
        'provider_key': identity.provider_key,
        'provider_label': identity.provider_label,
        'instance_name': identity.instance_name,
        'runtime_state': 'consumer_validation_required',
        'label': readiness['label'],
        'tone': readiness['tone'],
        'detail': identity.detail,
    }
    if not readiness['required_contract_ready']:
        blocker = metrics_validation_blocker(
            system,
            status=source.readiness.state,
            status_label=readiness['label'],
            detail=(
                str(readiness.get('detail') or '').strip()
                or (
                    f'{readiness["required_ready_count"]} of {readiness["required_total_count"]} required metrics are ready. '
                    f'Consumer validation status: {readiness["label"]}.'
                )
            ),
        )
        return source, source_view, readiness, blocker

    source_view.update(
        {
            'runtime_state': 'checking',
            'label': 'Checking Runtime',
            'tone': 'info',
            'detail': f'{identity.detail} · Required metric contract validated.',
        }
    )
    return source, source_view, readiness, None


def runtime_source_state(
    system: ObjectStorageSystem,
    source_view: dict[str, Any],
    reader: EvidenceReader,
) -> ObjectStorageDependencyBlocker | None:
    if reader.source_wide_failure is not None:
        exc = reader.source_wide_failure
        source_view['runtime_state'] = (
            'authentication_failed' if exc.kind == MetricsSourceFailureKind.AUTHENTICATION else 'disconnected'
        )
        source_view['label'] = (
            'Authentication Failed' if exc.kind == MetricsSourceFailureKind.AUTHENTICATION else 'Disconnected'
        )
        source_view['tone'] = 'critical'
        source_view['detail'] = str(exc)
        return metrics_runtime_blocker(system, exc)

    if reader.failed_query_count and reader.successful_query_count == 0:
        detail = reader.diagnostics[0] if reader.diagnostics else 'All runtime metric queries failed.'
        source_view['runtime_state'] = 'query_failed'
        source_view['label'] = 'Runtime Query Failed'
        source_view['tone'] = 'critical'
        source_view['detail'] = detail
        return metrics_query_blocker(system, detail=detail)

    if reader.failed_query_count:
        source_view['runtime_state'] = 'degraded'
        source_view['label'] = 'Degraded'
        source_view['tone'] = 'warning'
        source_view['detail'] = reader.diagnostics[0] if reader.diagnostics else 'One or more metric queries failed.'
        return None

    source_view['runtime_state'] = 'operational'
    source_view['label'] = 'Operational'
    source_view['tone'] = 'normal'
    source_view['detail'] = (
        f'{source_view.get("provider_label") or "Metrics source"} runtime queries completed successfully.'
    )
    return None
