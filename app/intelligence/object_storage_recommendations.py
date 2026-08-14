from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload, selectinload

from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem
from app.models.object_storage_analytics import ObjectStorageForecastSnapshot

QUOTA_WARNING_PERCENT = 85.0
QUOTA_CRITICAL_PERCENT = 95.0


def _format_bytes(value: int | float | None) -> str:
    if value is None:
        return 'N/A'
    size = float(value)
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')
    unit = units[0]
    for candidate in units:
        unit = candidate
        if abs(size) < 1024.0 or candidate == units[-1]:
            break
        size /= 1024.0
    precision = 0 if unit == 'B' else (1 if abs(size) >= 10 else 2)
    return f'{size:.{precision}f} {unit}'


def _format_percent(value: float | None) -> str:
    return f'{value:.1f}%' if value is not None else 'N/A'


def _provider_identity(system: ObjectStorageSystem) -> tuple[str, str]:
    if system.minio_connection is not None:
        return 'minio', 'MinIO'
    return '', 'Object Storage'


def _finding(
    rule: dict[str, Any],
    *,
    finding_key: str,
    title: str,
    summary: str,
    condition_summary: str,
    evidence: dict[str, Any],
    recommended_action: str | None = None,
    impact: str | None = None,
) -> dict[str, Any]:
    finding = dict(rule)
    finding.update(
        {
            'rule_key': finding_key,
            'title': title,
            'summary': summary,
            'condition_summary': condition_summary,
            'recommended_action': recommended_action or str(rule.get('recommended_action') or ''),
            'impact': impact or str(rule.get('impact') or ''),
            'status': 'available',
            'evidence': evidence,
        }
    )
    return finding


def _bucket_evidence(
    *,
    system: ObjectStorageSystem,
    bucket: ObjectStorageBucket,
    provider_key: str,
    provider_label: str,
    quota_utilization: float | None = None,
) -> dict[str, Any]:
    return {
        'asset_key': str(system.id),
        'object_storage_system_id': str(system.id),
        'system_name': system.name,
        'environment': system.environment,
        'provider_key': provider_key,
        'provider_label': provider_label,
        'bucket_id': str(bucket.id),
        'bucket_name': bucket.name,
        'usage_bytes': bucket.size_bytes,
        'usage_display': _format_bytes(bucket.size_bytes),
        'quota_bytes': bucket.quota_bytes,
        'quota_display': _format_bytes(bucket.quota_bytes),
        'quota_utilization': quota_utilization,
        'quota_utilization_display': _format_percent(quota_utilization),
        'exposure_state': str(bucket.exposure_state or 'not_collected'),
        'exposure_display': str(bucket.exposure_state or 'not_collected').replace('_', ' ').title(),
        'encryption_state': str(bucket.encryption_state or 'not_collected'),
        'encryption_display': str(bucket.encryption_state or 'not_collected').replace('_', ' ').title(),
        'inventory_observed_at': bucket.observed_at.isoformat() if bucket.observed_at is not None else '',
    }


def _quota_findings(
    *,
    rules: dict[str, dict[str, Any]],
    system: ObjectStorageSystem,
    bucket: ObjectStorageBucket,
    provider_key: str,
    provider_label: str,
) -> list[dict[str, Any]]:
    if bucket.size_bytes is None or bucket.quota_bytes is None or bucket.quota_bytes <= 0:
        return []

    quota_utilization = float(bucket.size_bytes) / float(bucket.quota_bytes) * 100.0
    if quota_utilization >= QUOTA_CRITICAL_PERCENT:
        rule = rules.get('object_storage.bucket.quota_critical')
    elif quota_utilization >= QUOTA_WARNING_PERCENT:
        rule = rules.get('object_storage.bucket.quota_pressure')
    else:
        rule = None
    if rule is None:
        return []

    evidence = _bucket_evidence(
        system=system,
        bucket=bucket,
        provider_key=provider_key,
        provider_label=provider_label,
        quota_utilization=quota_utilization,
    )
    return [
        _finding(
            rule,
            finding_key=f"{rule['rule_key']}:{system.id}:{bucket.id}",
            title=f'{bucket.name} quota utilization is {_format_percent(quota_utilization)}',
            summary=(
                f'Committed Object Storage inventory shows {bucket.name} using '
                f'{_format_bytes(bucket.size_bytes)} of {_format_bytes(bucket.quota_bytes)} configured quota.'
            ),
            condition_summary=(
                f'Bucket quota utilization is {_format_percent(quota_utilization)}; '
                f'the active review boundary begins at {QUOTA_WARNING_PERCENT:.0f}% and the critical boundary at '
                f'{QUOTA_CRITICAL_PERCENT:.0f}%.'
            ),
            evidence=evidence,
        )
    ]


def _governance_findings(
    *,
    rules: dict[str, dict[str, Any]],
    system: ObjectStorageSystem,
    bucket: ObjectStorageBucket,
    provider_key: str,
    provider_label: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    evidence = _bucket_evidence(
        system=system,
        bucket=bucket,
        provider_key=provider_key,
        provider_label=provider_label,
    )

    if str(bucket.exposure_state or '').strip().lower() == 'public':
        rule = rules.get('object_storage.bucket.public_exposure')
        if rule is not None:
            findings.append(
                _finding(
                    rule,
                    finding_key=f"{rule['rule_key']}:{system.id}:{bucket.id}",
                    title=f'{bucket.name} has public exposure evidence',
                    summary=(
                        f'Committed Object Storage inventory reports public exposure for bucket {bucket.name} '
                        f'on {system.name}.'
                    ),
                    condition_summary='Bucket exposure_state is public in the latest committed Object Storage inventory.',
                    evidence=evidence,
                )
            )

    if str(bucket.encryption_state or '').strip().lower() == 'not_configured':
        rule = rules.get('object_storage.bucket.encryption_not_configured')
        if rule is not None:
            findings.append(
                _finding(
                    rule,
                    finding_key=f"{rule['rule_key']}:{system.id}:{bucket.id}",
                    title=f'{bucket.name} has no configured encryption evidence',
                    summary=(
                        f'Committed Object Storage inventory reports encryption as not configured for bucket '
                        f'{bucket.name} on {system.name}.'
                    ),
                    condition_summary=(
                        'Bucket encryption_state is not_configured in the latest committed Object Storage inventory.'
                    ),
                    evidence=evidence,
                )
            )

    return findings



def _forecast_findings(
    *,
    rules: dict[str, dict[str, Any]],
    system: ObjectStorageSystem,
    provider_key: str,
    provider_label: str,
) -> list[dict[str, Any]]:
    snapshot = ObjectStorageForecastSnapshot.query.filter_by(
        object_storage_system_id=str(system.id),
        history_window='30d',
        method='linear-v1',
        status='ready',
    ).first()
    if snapshot is None or not isinstance(snapshot.payload_json, dict):
        return []
    expires_at = snapshot.expires_at
    if expires_at is None:
        return []
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires_at:
        return []

    forecast = snapshot.payload_json.get('forecast')
    if not isinstance(forecast, dict):
        return []
    days_to_capacity = forecast.get('days_to_capacity')
    growth_per_day = forecast.get('growth_per_day')
    if not isinstance(days_to_capacity, (int, float)) or not isinstance(growth_per_day, (int, float)):
        return []
    if float(growth_per_day) <= 0 or float(days_to_capacity) > 90.0:
        return []

    rule_key = (
        'object_storage.forecast.capacity_exhaustion_critical'
        if float(days_to_capacity) <= 30.0
        else 'object_storage.forecast.capacity_exhaustion_review'
    )
    rule = rules.get(rule_key)
    if rule is None:
        return []
    evidence = {
        'asset_key': str(system.id),
        'object_storage_system_id': str(system.id),
        'system_name': system.name,
        'environment': system.environment,
        'provider_key': provider_key,
        'provider_label': provider_label,
        'forecast_window': '30 Days',
        'capacity_eta_days': float(days_to_capacity),
        'capacity_eta_display': f'{float(days_to_capacity):.1f} days',
        'growth_per_day': float(growth_per_day),
        'growth_per_day_display': f'{_format_bytes(float(growth_per_day))}/day',
        'generated_at': snapshot.generated_at.isoformat() if snapshot.generated_at is not None else '',
    }
    return [
        _finding(
            rule,
            finding_key=f"{rule_key}:{system.id}:30d",
            title=f'{system.name} capacity exhaustion is projected in {float(days_to_capacity):.1f} days',
            summary=(
                f'The current 30-day Object Storage forecast for {system.name} projects positive growth of '
                f'{_format_bytes(float(growth_per_day))} per day and capacity exhaustion in '
                f'{float(days_to_capacity):.1f} days.'
            ),
            condition_summary=(
                'Current worker-materialized forecast evidence places projected capacity exhaustion inside '
                f'the {"30-day critical" if float(days_to_capacity) <= 30.0 else "90-day review"} boundary.'
            ),
            evidence=evidence,
        )
    ]

def build_object_storage_recommendation_findings(
    rules: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate committed Object Storage inventory for currently supported recommendations.

    The evaluator is provider-aware but domain-owned. MinIO is the first supported
    provider because KAORI currently has a validated MinIO inventory collector. No
    live provider, Prometheus, or Alertmanager query is issued from Intelligence.
    """

    systems = (
        ObjectStorageSystem.query.options(
            joinedload(ObjectStorageSystem.minio_connection),
            selectinload(ObjectStorageSystem.buckets),
        )
        .order_by(ObjectStorageSystem.name.asc())
        .all()
    )
    findings: list[dict[str, Any]] = []
    for system in systems:
        provider_key, provider_label = _provider_identity(system)
        if provider_key != 'minio':
            continue
        findings.extend(
            _forecast_findings(
                rules=rules,
                system=system,
                provider_key=provider_key,
                provider_label=provider_label,
            )
        )
        for bucket in system.buckets:
            findings.extend(
                _quota_findings(
                    rules=rules,
                    system=system,
                    bucket=bucket,
                    provider_key=provider_key,
                    provider_label=provider_label,
                )
            )
            findings.extend(
                _governance_findings(
                    rules=rules,
                    system=system,
                    bucket=bucket,
                    provider_key=provider_key,
                    provider_label=provider_label,
                )
            )
    return findings
