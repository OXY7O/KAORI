"""S3-compatible Object Storage transport adapter."""

from app.integrations.storage.object_storage.adapters.s3.client import (
    S3TransportFailure,
    build_s3_client,
    list_buckets,
)

__all__ = ['S3TransportFailure', 'build_s3_client', 'list_buckets']
