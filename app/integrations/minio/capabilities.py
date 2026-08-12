from __future__ import annotations

from app.integrations.contracts import CapabilityDefinition
from app.integrations.minio.compatibility import COMPATIBILITY_PROFILE_KEYS

API_CAPABILITIES = (
    CapabilityDefinition('s3_api', 'S3 API', 'Reach the registered S3-compatible API endpoint.', required=True),
    CapabilityDefinition(
        'bucket_discovery', 'Bucket Discovery', 'List buckets visible to the registered credential.', required=True
    ),
    CapabilityDefinition('bucket_versioning_read', 'Versioning Read', 'Read bucket versioning configuration.'),
    CapabilityDefinition('bucket_lifecycle_read', 'Lifecycle Read', 'Read bucket lifecycle configuration.'),
    CapabilityDefinition('bucket_policy_read', 'Bucket Policy Read', 'Read bucket policy configuration.'),
    CapabilityDefinition('bucket_encryption_read', 'Encryption Read', 'Read bucket encryption configuration.'),
    CapabilityDefinition('bucket_object_lock_read', 'Object Lock Read', 'Read bucket object-lock configuration.'),
)

CAPABILITY_KEYS = tuple(item.key for item in API_CAPABILITIES)
COMPATIBILITY_PROFILES = COMPATIBILITY_PROFILE_KEYS
CAPABILITY_PROFILE = 'minio-object-storage-api-v1'

OBJECT_STORAGE_SYSTEM_SCOPE = 'object_storage_system'

PROMETHEUS_CAPABILITY_SCOPE = (
    'object_storage.metrics.version',
    'object_storage.metrics.cluster',
    'object_storage.metrics.bucket',
    'object_storage.metrics.runtime',
)
