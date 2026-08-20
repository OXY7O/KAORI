from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from app.models.object_storage import ObjectStorageSystem
from app.storage.object_storage.analytics.analysis import error_ratio
from app.storage.object_storage.analytics.presentation import (
    format_bytes,
    format_number,
    format_percent,
    format_rate,
    utilization_percent,
    utilization_tone,
)
from app.storage.object_storage.analytics.runtime import EvidenceReader


@dataclass(frozen=True, slots=True)
class BucketMetricEvidence:
    usage: dict[str, float]
    objects: dict[str, float]
    quota: dict[str, float]
    request_rate: dict[str, float]
    error_rate: dict[str, float]
    usage_state: str
    objects_state: str
    quota_state: str
    request_state: str
    error_state: str


def _metric_evidence_label(state: str, *, bucket_scoped: bool = False) -> str:
    labels = {
        'unsupported': 'Metric Not Scraped',
        'blocked': 'Metric Contract Blocked',
        'not_validated': 'Validation Required',
        'failed': 'Runtime Query Failed',
        'skipped': 'Runtime Query Skipped',
        'no_data': 'No Current Samples',
    }
    if state == 'ready' and bucket_scoped:
        return 'No Bucket Series'
    return labels.get(state, 'Unavailable')


def _collect_metric_evidence(
    reader: EvidenceReader,
    *,
    include_activity: bool,
    include_capacity_detail: bool,
) -> BucketMetricEvidence:
    return BucketMetricEvidence(
        usage=reader.vector('object_storage.bucket.usage'),
        objects=reader.vector('object_storage.bucket.objects') if include_capacity_detail else {},
        quota=reader.vector('object_storage.bucket.quota') if include_capacity_detail else {},
        request_rate=reader.vector('object_storage.bucket.request_rate') if include_activity else {},
        error_rate=reader.vector('object_storage.bucket.error_rate') if include_activity else {},
        usage_state=reader.evidence_state('object_storage.bucket.usage'),
        objects_state=(
            reader.evidence_state('object_storage.bucket.objects') if include_capacity_detail else 'not_requested'
        ),
        quota_state=(
            reader.evidence_state('object_storage.bucket.quota') if include_capacity_detail else 'not_requested'
        ),
        request_state=(
            reader.evidence_state('object_storage.bucket.request_rate') if include_activity else 'not_requested'
        ),
        error_state=(
            reader.evidence_state('object_storage.bucket.error_rate') if include_activity else 'not_requested'
        ),
    )


def _resolve_inventory_fallback(
    metric_value: float | None,
    inventory_value: int | None,
    *,
    source_label: str,
    metric_state: str,
) -> tuple[float | None, str]:
    if metric_value is not None:
        return metric_value, source_label
    if inventory_value is not None:
        return float(inventory_value), 'Committed Snapshot'
    return None, _metric_evidence_label(metric_state, bucket_scoped=True)


def _resolve_quota(
    *,
    bucket: Any,
    metric_quota: float | None,
    source_label: str,
    metric_state: str,
) -> dict[str, Any]:
    if metric_quota is not None:
        return {
            'bytes': metric_quota,
            'state': 'configured',
            'source': source_label,
            'evidence_code': 'metrics_source',
        }
    if bucket is None:
        return {
            'bytes': None,
            'state': 'unknown',
            'source': _metric_evidence_label(metric_state, bucket_scoped=True),
            'evidence_code': None,
        }

    inventory_state = str(bucket.quota_state or 'not_collected').strip().lower().replace('-', '_')
    if bucket.quota_bytes is not None:
        return {
            'bytes': float(bucket.quota_bytes),
            'state': 'configured',
            'source': 'Committed Snapshot',
            'evidence_code': bucket.quota_evidence_code,
        }
    if inventory_state == 'not_configured':
        return {
            'bytes': None,
            'state': 'not_configured',
            'source': 'Committed Snapshot',
            'evidence_code': bucket.quota_evidence_code,
        }
    if inventory_state == 'not_collected':
        return {
            'bytes': None,
            'state': 'not_collected',
            'source': 'Inventory Quota Not Collected',
            'evidence_code': bucket.quota_evidence_code,
        }
    if inventory_state == 'not_supported':
        return {
            'bytes': None,
            'state': 'not_supported',
            'source': 'Inventory Quota Unsupported',
            'evidence_code': bucket.quota_evidence_code,
        }
    if inventory_state == 'configured':
        return {
            'bytes': None,
            'state': 'inconsistent',
            'source': 'Inventory Evidence Incomplete',
            'evidence_code': bucket.quota_evidence_code,
        }
    return {
        'bytes': None,
        'state': 'unknown',
        'source': _metric_evidence_label(metric_state, bucket_scoped=True),
        'evidence_code': bucket.quota_evidence_code,
    }


def _quota_presentation(
    *,
    quota_state: str,
    quota_bytes: float | None,
    quota_utilization: float | None,
    metric_state: str,
) -> dict[str, str]:
    state_views = {
        'not_configured': ('Not Configured', 'Not Applicable', 'No Quota Configured', 'info'),
        'inconsistent': ('Evidence Incomplete', 'Unknown', 'Review Inventory Evidence', 'warning'),
        'not_collected': ('N/A', 'Unknown', 'Quota Not Collected', 'warning'),
        'not_supported': ('N/A', 'Not Available', 'Quota Collection Unsupported', 'unknown'),
    }
    if quota_state in state_views:
        display, utilization_display, label, tone = state_views[quota_state]
        return {
            'display': display,
            'utilization_display': utilization_display,
            'status_label': label,
            'status_tone': tone,
        }
    if quota_bytes is None:
        return {
            'display': 'N/A',
            'utilization_display': 'N/A',
            'status_label': _metric_evidence_label(metric_state, bucket_scoped=True),
            'status_tone': 'unknown',
        }
    if quota_utilization is not None and quota_utilization >= 95:
        label, tone = 'Critical', 'critical'
    elif quota_utilization is not None and quota_utilization >= 85:
        label, tone = 'Pressure', 'warning'
    else:
        label, tone = 'Within Quota', 'normal'
    return {
        'display': format_bytes(quota_bytes),
        'utilization_display': format_percent(quota_utilization),
        'status_label': label,
        'status_tone': tone,
    }


def _build_bucket_row(
    *,
    name: str,
    bucket: Any,
    evidence: BucketMetricEvidence,
    source_label: str,
) -> dict[str, Any]:
    size, usage_source = _resolve_inventory_fallback(
        evidence.usage.get(name),
        bucket.size_bytes if bucket is not None else None,
        source_label=source_label,
        metric_state=evidence.usage_state,
    )
    object_count, objects_source = _resolve_inventory_fallback(
        evidence.objects.get(name),
        bucket.object_count if bucket is not None else None,
        source_label=source_label,
        metric_state=evidence.objects_state,
    )
    quota = _resolve_quota(
        bucket=bucket,
        metric_quota=evidence.quota.get(name),
        source_label=source_label,
        metric_state=evidence.quota_state,
    )
    bucket_request_rate = evidence.request_rate.get(name)
    bucket_error_rate = evidence.error_rate.get(name)
    request_source = (
        source_label
        if bucket_request_rate is not None
        else _metric_evidence_label(evidence.request_state, bucket_scoped=True)
    )
    error_source = (
        source_label
        if bucket_error_rate is not None
        else _metric_evidence_label(evidence.error_state, bucket_scoped=True)
    )
    bucket_error_ratio = error_ratio(bucket_error_rate, bucket_request_rate)
    quota_utilization = utilization_percent(size, quota['bytes'])
    quota_view = _quota_presentation(
        quota_state=str(quota['state']),
        quota_bytes=quota['bytes'],
        quota_utilization=quota_utilization,
        metric_state=evidence.quota_state,
    )
    return {
        'name': name,
        'usage_bytes': size,
        'usage_display': format_bytes(size),
        'usage_source': usage_source,
        'usage_evidence_state': evidence.usage_state,
        'objects': object_count,
        'objects_display': format_number(object_count),
        'objects_source': objects_source,
        'objects_evidence_state': evidence.objects_state,
        'quota_bytes': quota['bytes'],
        'quota_display': quota_view['display'],
        'quota_source': quota['source'],
        'quota_state': quota['state'],
        'quota_evidence_code': quota['evidence_code'],
        'quota_utilization': quota_utilization,
        'quota_utilization_display': quota_view['utilization_display'],
        'quota_tone': utilization_tone(quota_utilization) if quota['bytes'] is not None else 'unknown',
        'quota_status_label': quota_view['status_label'],
        'quota_status_tone': quota_view['status_tone'],
        'request_rate': bucket_request_rate,
        'request_rate_display': format_rate(bucket_request_rate),
        'request_source': request_source,
        'request_evidence_state': evidence.request_state,
        'error_rate': bucket_error_rate,
        'error_rate_display': format_rate(bucket_error_rate),
        'error_source': error_source,
        'error_evidence_state': evidence.error_state,
        'error_ratio': bucket_error_ratio,
        'error_ratio_display': format_percent(bucket_error_ratio),
        'source': usage_source,
    }


def build_bucket_rows(
    system: ObjectStorageSystem,
    reader: EvidenceReader,
    *,
    include_activity: bool,
    include_capacity_detail: bool = True,
) -> list[dict[str, Any]]:
    evidence = _collect_metric_evidence(
        reader,
        include_activity=include_activity,
        include_capacity_detail=include_capacity_detail,
    )
    inventory = {bucket.name: bucket for bucket in system.buckets or ()}
    names = (
        set(inventory)
        | set(evidence.usage)
        | set(evidence.objects)
        | set(evidence.quota)
        | set(evidence.request_rate)
        | set(evidence.error_rate)
    )
    rows = [
        _build_bucket_row(
            name=name,
            bucket=inventory.get(name),
            evidence=evidence,
            source_label=reader.source_label,
        )
        for name in names
    ]
    rows.sort(key=lambda item: float(item['usage_bytes'] or 0), reverse=True)
    return rows


def add_bucket_usage_shares(rows: list[dict[str, Any]], usage_total: float | None) -> None:
    for row in rows:
        row['usage_share'] = utilization_percent(row.get('usage_bytes'), usage_total)
        row['usage_share_display'] = format_percent(row['usage_share'])


def _forecast_watch(
    *,
    history_state: str,
    days_to_quota: float | None,
    projected_quota_utilization: float | None,
    growth_per_day: float | None,
) -> tuple[str, str]:
    if history_state != 'ready':
        return 'Insufficient History', 'unknown'
    if days_to_quota is not None and days_to_quota <= 30:
        return 'Critical · Quota ≤ 30d', 'critical'
    if days_to_quota is not None and days_to_quota <= 90:
        return 'Warning · Quota ≤ 90d', 'warning'
    if projected_quota_utilization is not None and projected_quota_utilization >= 95:
        return 'Critical · Projected ≥ 95%', 'critical'
    if projected_quota_utilization is not None and projected_quota_utilization >= 85:
        return 'Warning · Projected ≥ 85%', 'warning'
    if growth_per_day is not None and growth_per_day > 0:
        return 'Growth Watch', 'info'
    if growth_per_day is not None:
        return 'Stable / Decreasing', 'normal'
    return 'Insufficient History', 'unknown'


def _history_label(history_state: str) -> str:
    labels = {
        'ready': 'Forecast Ready',
        'partial': 'One Range Sample',
        'no_data': 'No Range Series',
    }
    return labels.get(history_state, 'No Range Series')


def _forecast_row(raw: dict[str, Any]) -> dict[str, Any]:
    forecast_value = raw.get('forecast')
    forecast = cast(dict[str, Any], forecast_value) if isinstance(forecast_value, dict) else {}
    sample_count = int(raw.get('sample_count') or 0)
    history_state = str(raw.get('history_state') or ('ready' if sample_count >= 2 else 'no_data'))
    current = raw.get('current_bytes')
    inventory_usage = raw.get('inventory_usage_bytes')
    quota = raw.get('quota_bytes')
    projected_30d = forecast.get('projected_30d')
    days_to_quota = forecast.get('days_to_capacity')
    growth_per_day = forecast.get('growth_per_day')
    quota_utilization = utilization_percent(current, quota)
    projected_quota_utilization = utilization_percent(projected_30d, quota)
    watch_label, watch_tone = _forecast_watch(
        history_state=history_state,
        days_to_quota=days_to_quota,
        projected_quota_utilization=projected_quota_utilization,
        growth_per_day=growth_per_day,
    )
    return {
        'name': str(raw.get('name') or 'Unknown Bucket'),
        'sample_count': sample_count,
        'history_state': history_state,
        'history_label': _history_label(history_state),
        'history_tone': 'normal' if history_state == 'ready' else 'unknown',
        'current_bytes': current,
        'current_display': format_bytes(current),
        'inventory_usage_bytes': inventory_usage,
        'inventory_usage_display': format_bytes(inventory_usage),
        'growth_per_day': growth_per_day,
        'growth_per_day_display': format_bytes(growth_per_day) + '/day' if growth_per_day is not None else 'N/A',
        'projected_30d': projected_30d,
        'projected_30d_display': format_bytes(projected_30d),
        'quota_bytes': quota,
        'quota_display': format_bytes(quota) if quota is not None else 'Not Configured',
        'quota_utilization': quota_utilization,
        'quota_utilization_display': format_percent(quota_utilization),
        'projected_quota_utilization': projected_quota_utilization,
        'projected_quota_utilization_display': format_percent(projected_quota_utilization),
        'days_to_quota': days_to_quota,
        'days_to_quota_display': f'{days_to_quota:.1f} days' if days_to_quota is not None else 'No ETA',
        'watch_label': watch_label,
        'watch_tone': watch_tone,
    }


def build_bucket_forecast_view(raw_rows: object) -> list[dict[str, Any]]:
    rows = [_forecast_row(raw) for raw in raw_rows if isinstance(raw, dict)] if isinstance(raw_rows, list) else []
    tone_order = {'critical': 4, 'warning': 3, 'info': 2, 'unknown': 1, 'normal': 0}
    rows.sort(
        key=lambda row: (
            tone_order.get(str(row['watch_tone']), 1),
            float(row.get('projected_30d') or row.get('current_bytes') or row.get('inventory_usage_bytes') or 0),
        ),
        reverse=True,
    )
    return rows


def build_bucket_forecast_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        'tracked_count': len(rows),
        'ready_count': sum(row.get('history_state') == 'ready' for row in rows),
        'attention_count': sum(row.get('watch_tone') in {'critical', 'warning'} for row in rows),
        'critical_count': sum(row.get('watch_tone') == 'critical' for row in rows),
        'warning_count': sum(row.get('watch_tone') == 'warning' for row in rows),
        'quota_bounded_count': sum(row.get('quota_bytes') is not None for row in rows),
        'history_gap_count': sum(row.get('history_state') != 'ready' for row in rows),
    }
