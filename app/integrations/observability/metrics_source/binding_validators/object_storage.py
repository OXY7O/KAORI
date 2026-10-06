from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.extensions.db import db
from app.integrations.managed_assets import object_storage_owner
from app.integrations.observability.metrics_source.binding_profiles import BindingValidationProfile
from app.integrations.observability.metrics_source.binding_validators.contracts import BindingValidationAssessment
from app.integrations.observability.metrics_source.query_profiles.object_storage_audit import (
    ObjectStorageMetricsProfileAuditor,
)
from app.models.integration import IntegrationBinding
from app.models.object_storage import ObjectStorageSystem

AuditFactory = Callable[[Any], ObjectStorageMetricsProfileAuditor]
SupportPredicate = Callable[[ObjectStorageSystem], bool]


@dataclass(frozen=True, slots=True)
class ObjectStorageValidationAdapter:
    """Qualified Object Storage provider + Metrics Source validation profile."""

    asset_profile: str
    profile_label: str
    supports: SupportPredicate
    audit_factory: AuditFactory


def _supports_minio(system: ObjectStorageSystem) -> bool:
    owner = object_storage_owner(system.id)
    return owner is not None and owner.provider_key == 'minio'


_VALIDATION_ADAPTERS: tuple[ObjectStorageValidationAdapter, ...] = (
    ObjectStorageValidationAdapter(
        asset_profile='minio-v2',
        profile_label='MinIO Metrics v2',
        supports=_supports_minio,
        audit_factory=ObjectStorageMetricsProfileAuditor,
    ),
)


def _resolve_validation_adapter(system: ObjectStorageSystem) -> ObjectStorageValidationAdapter | None:
    return next((adapter for adapter in _VALIDATION_ADAPTERS if adapter.supports(system)), None)


def validate_object_storage_binding(
    *,
    client: Any,
    binding: IntegrationBinding,
    profile: BindingValidationProfile,
) -> BindingValidationAssessment:
    system = db.session.get(ObjectStorageSystem, binding.asset_key)
    if system is None:
        return BindingValidationAssessment(
            status='blocked',
            message='The Object Storage system referenced by this binding no longer exists.',
        )

    adapter = _resolve_validation_adapter(system)
    if adapter is None:
        return BindingValidationAssessment(
            status='blocked',
            message=(
                'No provider-qualified Metrics Source validation adapter is registered for this Object Storage system. '
                'Register an adapter for the asset provider before validating the metrics binding.'
            ),
            evidence={
                'metrics_readiness': {
                    'profile': 'unregistered',
                    'profile_label': 'No Qualified Metrics Profile',
                    'status': 'blocked',
                    'checked_at': None,
                    'summary': {'total': 0, 'ready': 0, 'no_data': 0, 'unsupported': 0, 'blocked': 0},
                    'domain_summary': [],
                    'items': [],
                }
            },
        )

    audit = adapter.audit_factory(client).audit(execute_queries=True)
    summary = audit.get('summary') or {}
    observed_metrics = set(audit.get('observed_metrics') or ())
    identity_metrics = {
        'minio_cluster_capacity_usable_total_bytes',
        'minio_cluster_usage_total_bytes',
        'minio_cluster_bucket_total',
    }
    matched_identity = sorted(identity_metrics & observed_metrics)
    matched_series = sum(
        int(item.get('series_count') or 0)
        for item in (audit.get('items') or [])
        if isinstance(item, dict) and set(item.get('required_metrics') or ()) & identity_metrics
    )

    if not matched_identity:
        status = 'degraded'
        message = profile.no_match_message
        matched_signal = None
    else:
        status = 'ready'
        matched_signal = matched_identity[0]
        readiness_status = str(audit.get('status') or 'partial')
        if readiness_status == 'ready':
            message = f'{profile.label} resolved {adapter.profile_label} and validated all required canonical metrics.'
        else:
            message = (
                f'{profile.label} resolved {adapter.profile_label} and collected partial canonical metric evidence. '
                'The binding remains usable while Analytics exposes the exact readiness gaps.'
            )

    return BindingValidationAssessment(
        status=status,
        message=message,
        matched_series=matched_series,
        matched_signal=matched_signal,
        evidence={
            'asset_profile': adapter.asset_profile,
            'asset_profile_label': adapter.profile_label,
            'metrics_readiness': audit,
            'available_capabilities': [],
            'capability_assessments': [],
            'required_metric_summary': {
                'ready': int(summary.get('required_ready') or 0),
                'total': int(summary.get('required_total') or 0),
                'blocked': int(summary.get('required_blocked') or 0),
                'no_data': int(summary.get('required_no_data') or 0),
            },
        },
    )
