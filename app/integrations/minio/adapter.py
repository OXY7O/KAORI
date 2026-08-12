from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.minio.binding import ensure_primary_asset_binding, validate_asset_binding
from app.integrations.minio.capabilities import CAPABILITY_KEYS, CAPABILITY_PROFILE
from app.integrations.minio.client import test_instance_connection
from app.integrations.minio.compatibility import evaluate_minio_release
from app.integrations.runtime.scoring import calculate_health
from app.models.minio import MinioInstance


def _health_factors(instance: MinioInstance) -> tuple[HealthFactor, ...]:
    connected = instance.last_status == 'connected'
    compatibility_ready = instance.compatibility_status == 'compatible'
    latency_observed = instance.last_response_time_ms is not None
    high_latency = (instance.last_response_time_ms or 0) > 1500
    return (
        HealthFactor(
            'connectivity',
            'S3 API connectivity',
            'success' if connected else ('failed' if instance.last_status else 'unknown'),
            50,
            100 if connected else (0 if instance.last_status else 50),
            instance.last_error or '',
        ),
        HealthFactor(
            'compatibility',
            'MinIO compatibility',
            'success' if compatibility_ready else ('failed' if instance.compatibility_status else 'unknown'),
            35,
            100 if compatibility_ready else (0 if instance.compatibility_status else 50),
            instance.validation_message or '',
        ),
        HealthFactor(
            'latency',
            'API latency',
            'warning' if high_latency else ('success' if latency_observed else 'unknown'),
            15,
            60 if high_latency else (100 if latency_observed else 50),
            '',
        ),
    )


def _diagnostics(instance: MinioInstance) -> tuple[DiagnosticResult, ...]:
    connected = instance.last_status == 'connected'
    compatibility_ready = instance.compatibility_status == 'compatible'
    bucket_count = int((instance.validation_summary or {}).get('bucket_count') or 0)
    api_detail = (
        f'{instance.detected_product or "S3-compatible endpoint"}; {bucket_count} bucket(s) visible.'
        if connected
        else instance.last_error or 'API validation has not been observed.'
    )
    return (
        DiagnosticResult(
            key='s3_api',
            label='MinIO S3 API',
            category='connectivity',
            status='success' if connected else ('failed' if instance.last_status else 'unknown'),
            detail=api_detail,
            duration_ms=instance.last_response_time_ms,
            severity='critical' if instance.last_status and not connected else 'info',
            recommendation=(
                'Review endpoint, access key, secret key, TLS trust, and S3 permissions.'
                if instance.last_status and not connected
                else None
            ),
        ),
        DiagnosticResult(
            key='compatibility',
            label='Compatibility Profile',
            category='compatibility',
            status='success' if compatibility_ready else ('failed' if instance.compatibility_status else 'unknown'),
            detail=instance.validation_message or 'Run Full Validation to resolve the MinIO compatibility profile.',
            severity='critical' if instance.compatibility_status and not compatibility_ready else 'info',
        ),
    )


def _snapshot_metadata(instance: MinioInstance) -> dict[str, Any]:
    return {
        'asset_type': 'object_storage_system',
        'asset_key': instance.object_storage_system_id,
        'declared_release': instance.declared_release,
        'detected_product': instance.detected_product,
        'bucket_count': int((instance.validation_summary or {}).get('bucket_count') or 0),
        'deployment_id': instance.deployment_id,
    }


class MinioRuntimeAdapter:
    provider = 'minio'

    def refresh(self, instance: MinioInstance) -> dict[str, Any]:
        compatibility = evaluate_minio_release(instance.declared_release)
        now = datetime.now(UTC)
        result = test_instance_connection(instance)
        product_ready = result.product == 'minio'

        instance.detected_product = result.product
        instance.observed_server_header = result.server_header
        instance.deployment_id = result.deployment_id
        instance.compatibility_status = compatibility.status
        instance.compatibility_profile = compatibility.profile_key
        instance.capability_profile = CAPABILITY_PROFILE
        instance.capabilities = list(CAPABILITY_KEYS)
        instance.last_response_time_ms = result.latency_ms
        instance.last_validated_at = now
        instance.last_checked_at = now
        instance.last_status = 'connected'
        instance.last_error = None
        instance.validation_summary = {
            'bucket_count': result.bucket_count,
            'sample_buckets': list(result.bucket_names[:10]),
            'server_header': result.server_header,
            'deployment_id': result.deployment_id,
            'detected_product': result.product,
            'identity_evidence': result.identity_evidence,
        }

        if not product_ready:
            instance.readiness_status = 'blocked'
            instance.compatibility_status = 'product_mismatch'
            instance.compatibility_profile = None
            instance.validation_message = (
                'The S3 API is reachable, but Core Validation could not confirm MinIO product identity '
                'from the deployment header, server header, or MinIO liveness endpoint. '
                'Review the S3 API endpoint and any reverse proxy that filters MinIO health paths or response headers.'
            )
            instance.object_storage_system.status = 'blocked'
        elif compatibility.readiness == 'ready':
            instance.readiness_status = 'ready'
            instance.validation_message = (
                f'MinIO S3 API is reachable and listed {result.bucket_count} bucket(s). {compatibility.message}'
            )
            instance.object_storage_system.status = 'connected'
        else:
            instance.readiness_status = 'blocked'
            instance.validation_message = compatibility.message
            instance.object_storage_system.status = 'blocked'
        instance.object_storage_system.last_check = now

        canonical = instance.integration_instance
        canonical.readiness_status = instance.readiness_status
        canonical.health_status = instance.last_status
        canonical.last_checked_at = now
        canonical.last_error = instance.validation_message if instance.readiness_status == 'blocked' else None
        metadata = dict(canonical.metadata_json or {})
        metadata.update(
            {
                'asset_type': 'object_storage_system',
                'asset_key': instance.object_storage_system_id,
                'endpoint_product': 'minio',
                'declared_release': instance.declared_release,
            }
        )
        canonical.metadata_json = metadata
        db.session.flush()

        return {
            'success': instance.readiness_status == 'ready',
            'connected': True,
            'readiness_status': instance.readiness_status,
            'compatibility_status': instance.compatibility_status,
            'compatibility_profile': instance.compatibility_profile,
            'capability_profile': instance.capability_profile,
            'capabilities': list(instance.capabilities or []),
            'bucket_count': result.bucket_count,
            'latency_ms': result.latency_ms,
            'validation_message': instance.validation_message,
        }

    def refresh_health(self, instance: MinioInstance) -> dict[str, Any]:
        result = test_instance_connection(instance)
        now = datetime.now(UTC)
        instance.last_checked_at = now
        instance.last_response_time_ms = result.latency_ms
        instance.last_status = 'connected'
        instance.last_error = None
        instance.object_storage_system.status = 'connected'
        instance.object_storage_system.last_check = now
        db.session.flush()
        return {
            'success': True,
            'connected': True,
            'latency_ms': result.latency_ms,
            'bucket_count': result.bucket_count,
            'message': 'MinIO S3 API health check completed.',
        }

    def execute(self, operation: str, instance: MinioInstance, **kwargs: Any):
        if operation == 'connection.test':
            return self.refresh_health(instance)
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
        if operation == 'binding.create':
            return ensure_primary_asset_binding(instance, commit=bool(kwargs.get('commit', True)))
        if operation == 'binding.validate':
            binding = kwargs.get('binding')
            if binding is None:
                raise ValueError('MinIO binding.validate requires a binding.')
            return validate_asset_binding(
                instance=instance,
                binding=binding,
                commit=bool(kwargs.get('commit', True)),
            )
        raise ValueError(f'Unsupported MinIO integration operation: {operation}')

    def get_state(
        self,
        instance: MinioInstance,
        *,
        validation_result: dict[str, Any] | None = None,
    ) -> RuntimeState:
        del validation_result
        now = datetime.now(UTC)
        connected = instance.last_status == 'connected'
        readiness = instance.readiness_status or 'validation_required'
        observed_at = instance.last_checked_at or instance.last_validated_at or now
        return RuntimeState(
            provider=self.provider,
            instance_id=str(instance.id),
            instance_name=instance.name,
            observed_at=observed_at,
            readiness=readiness,
            health=calculate_health(_health_factors(instance)),
            diagnostics=_diagnostics(instance),
            snapshot=CapabilitySnapshot(
                profile=instance.capability_profile,
                compatibility_profile=instance.compatibility_profile,
                capabilities=tuple(sorted(instance.capabilities or ())),
                observed_at=observed_at,
                metadata=_snapshot_metadata(instance),
            ),
            last_success_at=instance.last_checked_at if connected else None,
            last_failure_at=instance.last_checked_at if instance.last_status and not connected else None,
            latency_ms=instance.last_response_time_ms,
            message=instance.validation_message
            or instance.last_error
            or 'Run Full Validation to observe this MinIO provider.',
        )


runtime_adapter = MinioRuntimeAdapter()
