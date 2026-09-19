from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.runtime.scoring import calculate_health
from app.integrations.storage.object_storage.providers.minio.capabilities import CAPABILITY_KEYS, CAPABILITY_PROFILE
from app.integrations.storage.object_storage.providers.minio.client import (
    probe_instance_runtime_health,
    test_instance_connection,
)
from app.integrations.storage.object_storage.providers.minio.compatibility import evaluate_minio_release
from app.models.minio import MinioInstance


def _health_factors(instance: MinioInstance) -> tuple[HealthFactor, ...]:
    connected = instance.last_status == 'connected'
    compatibility_ready = instance.compatibility_status in {'compatible', 'compatible_with_warnings'}
    compatibility_unverified = instance.compatibility_status in {
        'unverified_version',
        'version_unknown',
        'product_unqualified',
    }
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
            'success'
            if compatibility_ready
            else (
                'warning' if compatibility_unverified else ('failed' if instance.compatibility_status else 'unknown')
            ),
            35,
            100
            if compatibility_ready
            else (70 if compatibility_unverified else (0 if instance.compatibility_status else 50)),
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
    compatibility_ready = instance.compatibility_status in {'compatible', 'compatible_with_warnings'}
    compatibility_unverified = instance.compatibility_status in {
        'unverified_version',
        'version_unknown',
        'product_unqualified',
    }
    api_detail = (
        f'{instance.detected_product or "S3-compatible endpoint"} runtime endpoint is reachable.'
        if connected
        else instance.last_error or 'Runtime health has not been observed.'
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
                'Review endpoint, TLS trust, network access, and provider runtime health.'
                if instance.last_status and not connected
                else None
            ),
        ),
        DiagnosticResult(
            key='compatibility',
            label='Compatibility Profile',
            category='compatibility',
            status='success'
            if compatibility_ready
            else (
                'warning' if compatibility_unverified else ('failed' if instance.compatibility_status else 'unknown')
            ),
            detail=instance.validation_message or 'Run Full Validation to resolve the MinIO compatibility profile.',
            severity='warning'
            if compatibility_unverified
            else ('critical' if instance.compatibility_status and not compatibility_ready else 'info'),
        ),
    )


def _snapshot_metadata(instance: MinioInstance) -> dict[str, Any]:
    return {
        'asset_type': 'object_storage_system',
        'asset_key': instance.object_storage_system_id,
        'declared_release': instance.declared_release,
        'detected_product': instance.detected_product,
        'deployment_id': instance.deployment_id,
        'inventory_owner': 'job_execution',
    }


class MinioRuntimeAdapter:
    integration_type = 'object_storage'

    def refresh(self, instance: MinioInstance) -> dict[str, Any]:
        """Run Full Validation without committing object-storage inventory."""
        now = datetime.now(UTC)
        result = test_instance_connection(instance)
        compatibility = evaluate_minio_release(instance.declared_release, product=result.product)
        product_identified = result.product != 's3_compatible'

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
            'server_header': result.server_header,
            'deployment_id': result.deployment_id,
            'detected_product': result.product,
            'identity_evidence': result.identity_evidence,
            'compatibility_supported_range': compatibility.supported_range,
            'bucket_discovery_capability': 'available',
            'inventory_owner': 'job_execution',
        }

        if not product_identified:
            instance.readiness_status = 'blocked'
            instance.compatibility_status = 'product_mismatch'
            instance.compatibility_profile = None
            instance.validation_message = (
                'The S3 API is reachable, but Full Validation could not confirm MinIO product identity '
                'from the deployment header, server header, or MinIO liveness endpoint. '
                'Review the S3 API endpoint and any reverse proxy that filters MinIO health paths or response headers.'
            )
            instance.object_storage_system.status = 'blocked'
        elif compatibility.readiness == 'ready':
            instance.readiness_status = 'ready'
            instance.validation_message = (
                f'MinIO S3 access and bucket discovery satisfy {CAPABILITY_PROFILE}. {compatibility.message}'
            )
            instance.object_storage_system.status = 'connected'
        elif compatibility.readiness == 'degraded':
            instance.readiness_status = 'degraded'
            instance.validation_message = (
                f'MinIO S3 access and bucket discovery satisfy {CAPABILITY_PROFILE}. {compatibility.message}'
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
                'endpoint_product': result.product,
                'declared_release': instance.declared_release,
                'inventory_owner': 'job_execution',
            }
        )
        canonical.metadata_json = metadata
        db.session.flush()

        return {
            'success': instance.readiness_status != 'blocked',
            'connected': True,
            'readiness_status': instance.readiness_status,
            'compatibility_status': instance.compatibility_status,
            'compatibility_profile': instance.compatibility_profile,
            'capability_profile': instance.capability_profile,
            'capabilities': list(instance.capabilities or []),
            'latency_ms': result.latency_ms,
            'validation_message': instance.validation_message,
            'inventory_owner': 'job_execution',
        }

    def refresh_health(self, instance: MinioInstance) -> dict[str, Any]:
        """Refresh lightweight endpoint health without capability or inventory discovery."""
        result = probe_instance_runtime_health(instance)
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
            'status_code': result.status_code,
            'probe': result.probe,
            'message': 'MinIO runtime health probe completed without inventory discovery.',
        }

    def execute(self, operation: str, instance: MinioInstance, **kwargs: Any):
        if operation == 'connection.test':
            result = test_instance_connection(instance)
            return {
                'success': result.connected,
                'connected': result.connected,
                'latency_ms': result.latency_ms,
                'product': result.product,
                'identity_evidence': result.identity_evidence,
            }
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
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
            integration_type=self.integration_type,
            provider_key=instance.provider_key,
            adapter_key=instance.adapter_key,
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
