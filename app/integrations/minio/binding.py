from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.lifecycle import bind_instance, ensure_canonical_instance
from app.integrations.minio.capabilities import CAPABILITY_KEYS, OBJECT_STORAGE_SYSTEM_SCOPE
from app.models.integration import IntegrationBinding
from app.models.minio import MinioInstance


def ensure_primary_asset_binding(instance: MinioInstance, *, commit: bool = True) -> IntegrationBinding:
    canonical = ensure_canonical_instance(instance, provider_type='minio')
    binding = bind_instance(
        canonical,
        asset_type=OBJECT_STORAGE_SYSTEM_SCOPE,
        asset_key=instance.object_storage_system_id,
        role='primary',
        priority=100,
        capability_scope=list(CAPABILITY_KEYS),
        validation_status='validation_required',
        validation_message='Validate the MinIO API runtime before KAORI selects this provider for the object-storage asset.',
    )
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return binding


def validate_asset_binding(
    *,
    instance: MinioInstance,
    binding: IntegrationBinding,
    commit: bool = True,
) -> dict[str, Any]:
    expected_key = str(instance.object_storage_system_id)
    if binding.integration_instance_id != instance.integration_instance_id:
        raise ValueError('The selected binding does not belong to this MinIO provider.')
    if binding.asset_type != OBJECT_STORAGE_SYSTEM_SCOPE or binding.asset_key != expected_key:
        binding.validation_status = 'blocked'
        binding.validation_message = 'The MinIO provider binding does not target its canonical object-storage asset.'
    elif instance.readiness_status == 'ready':
        binding.validation_status = 'ready'
        binding.validation_message = 'MinIO API runtime and canonical object-storage asset identity are ready.'
    elif instance.readiness_status == 'blocked':
        binding.validation_status = 'blocked'
        binding.validation_message = instance.validation_message or 'MinIO API validation is blocked.'
    else:
        binding.validation_status = 'degraded'
        binding.validation_message = (
            instance.validation_message or 'Run MinIO Full Validation to refresh API readiness.'
        )
    binding.last_validated_at = datetime.now(UTC)
    if commit:
        db.session.commit()
    return {
        'status': binding.validation_status,
        'message': binding.validation_message,
        'asset_type': binding.asset_type,
        'asset_key': binding.asset_key,
    }
