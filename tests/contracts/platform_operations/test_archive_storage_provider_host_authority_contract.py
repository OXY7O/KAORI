"""Storage provider labels must use parsed URL authority, not text fragments."""

from __future__ import annotations

import pytest

from app.platform_operations.data_lifecycle.retention.storage_presentation import _storage_provider_label


@pytest.mark.parametrize(
    ('backend', 'endpoint', 'expected'),
    [
        ('local', 'https://attacker.invalid/minio', 'Local filesystem'),
        ('s3', None, 'Amazon S3'),
        ('s3', '', 'Amazon S3'),
        ('s3', 'https://s3.us-east-1.amazonaws.com', 'Amazon S3'),
        ('s3', 'https://bucket.s3.amazonaws.com', 'Amazon S3'),
        ('s3', 'https://s3.cn-north-1.amazonaws.com.cn', 'Amazon S3'),
        ('s3', 'https://minio.internal.invalid:9000', 'MinIO'),
        ('s3', 'https://minio-01.internal.invalid', 'MinIO'),
        ('s3', 'http://gateway.internal.invalid:9001', 'MinIO'),
        ('s3', 'https://gateway.internal.invalid', 'S3-compatible'),
        ('s3', 'https://gateway.internal.invalid/minio', 'S3-compatible'),
        ('s3', 'https://gateway.internal.invalid/?target=minio', 'S3-compatible'),
        ('s3', 'https://gateway.internal.invalid/?port=:9000', 'S3-compatible'),
        ('s3', 'https://notminio.internal.invalid', 'S3-compatible'),
        ('s3', 'https://amazonaws.com.attacker.invalid', 'S3-compatible'),
        ('s3', 'https://gateway.invalid/?target=amazonaws.com', 'S3-compatible'),
        ('s3', 'https://gateway.invalid:badport', 'S3-compatible'),
    ],
)
def test_archive_storage_provider_requires_parsed_endpoint_authority(
    backend: str, endpoint: str | None, expected: str
) -> None:
    assert _storage_provider_label(backend, endpoint) == expected
