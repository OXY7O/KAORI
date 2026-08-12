from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import boto3
import requests
from botocore.config import Config as BotoCoreConfig
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ProxyConnectionError,
    ReadTimeoutError,
    SSLError,
)
from requests import RequestException

from app.models.minio import MinioInstance


class MinioConnectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MinioBucketSummary:
    name: str
    creation_date: datetime | None


@dataclass(frozen=True, slots=True)
class MinioConnectionResult:
    connected: bool
    latency_ms: int
    bucket_count: int
    bucket_names: tuple[str, ...]
    server_header: str | None
    deployment_id: str | None
    product: str
    identity_evidence: str
    bucket_inventory: tuple[MinioBucketSummary, ...] = ()


@dataclass(frozen=True, slots=True)
class MinioInventoryResult:
    latency_ms: int
    buckets: tuple[MinioBucketSummary, ...]


@dataclass(frozen=True, slots=True)
class MinioRuntimeProbeResult:
    connected: bool
    latency_ms: int
    status_code: int
    probe: str


def build_s3_client(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
    addressing_style: str,
    timeout: int,
    verify_ssl: bool,
):
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region or 'us-east-1',
        verify=verify_ssl,
        config=BotoCoreConfig(
            signature_version='s3v4',
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={'max_attempts': 1, 'mode': 'standard'},
            s3={'addressing_style': addressing_style or 'path'},
        ),
    )


def _list_buckets_values(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
    addressing_style: str,
    timeout: int,
    verify_ssl: bool,
) -> tuple[dict[str, Any], int]:
    client = build_s3_client(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        addressing_style=addressing_style,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    started = perf_counter()
    try:
        payload: dict[str, Any] = client.list_buckets()
    except ClientError as exc:
        raise MinioConnectionError(_client_error_message(exc)) from exc
    except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, ProxyConnectionError) as exc:
        raise MinioConnectionError(
            'KAORI could not reach the MinIO S3 API endpoint. Verify the API URL, port, network route, and proxy settings.'
        ) from exc
    except SSLError as exc:
        raise MinioConnectionError(
            'TLS validation failed for the MinIO S3 API endpoint. Verify the certificate chain or disable TLS verification only for an approved internal exception.'
        ) from exc
    except (BotoCoreError, OSError) as exc:
        raise MinioConnectionError(f'MinIO S3 API validation failed: {exc}') from exc
    latency_ms = max(int((perf_counter() - started) * 1000), 0)
    return payload, latency_ms


def _bucket_inventory(payload: dict[str, Any]) -> tuple[MinioBucketSummary, ...]:
    return tuple(
        sorted(
            (
                MinioBucketSummary(
                    name=str(item.get('Name') or '').strip(),
                    creation_date=item.get('CreationDate') if isinstance(item.get('CreationDate'), datetime) else None,
                )
                for item in payload.get('Buckets') or []
                if str(item.get('Name') or '').strip()
            ),
            key=lambda item: item.name,
        )
    )


def test_connection_values(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str = 'us-east-1',
    addressing_style: str = 'path',
    timeout: int = 5,
    verify_ssl: bool = True,
) -> MinioConnectionResult:
    payload, latency_ms = _list_buckets_values(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        addressing_style=addressing_style,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    metadata = payload.get('ResponseMetadata') or {}
    headers = metadata.get('HTTPHeaders') or {}
    server_header = str(headers.get('server') or '').strip() or None
    deployment_id = str(headers.get('x-minio-deployment-id') or '').strip() or None
    product, identity_evidence = _detect_product_identity(
        endpoint=endpoint,
        timeout=timeout,
        verify_ssl=verify_ssl,
        server_header=server_header,
        deployment_id=deployment_id,
    )
    bucket_inventory = _bucket_inventory(payload)
    buckets = tuple(item.name for item in bucket_inventory)
    return MinioConnectionResult(
        connected=True,
        latency_ms=latency_ms,
        bucket_count=len(buckets),
        bucket_names=buckets,
        server_header=server_header,
        deployment_id=deployment_id,
        product=product,
        identity_evidence=identity_evidence,
        bucket_inventory=bucket_inventory,
    )


def collect_bucket_inventory_values(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str = 'us-east-1',
    addressing_style: str = 'path',
    timeout: int = 5,
    verify_ssl: bool = True,
) -> MinioInventoryResult:
    """Collect bucket records for the Inventory Job without changing provider validation state."""
    payload, latency_ms = _list_buckets_values(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        addressing_style=addressing_style,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    return MinioInventoryResult(
        latency_ms=latency_ms,
        buckets=_bucket_inventory(payload),
    )


def collect_instance_bucket_inventory(instance: MinioInstance) -> MinioInventoryResult:
    return collect_bucket_inventory_values(
        endpoint=instance.endpoint,
        access_key=instance.access_key,
        secret_key=instance.secret_key,
        region=instance.region,
        addressing_style=instance.addressing_style,
        timeout=instance.timeout,
        verify_ssl=instance.verify_ssl,
    )


def probe_runtime_values(
    *,
    endpoint: str,
    timeout: int = 5,
    verify_ssl: bool = True,
    product: str | None = None,
) -> MinioRuntimeProbeResult:
    """Run a lightweight provider health probe without collecting inventory."""
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise MinioConnectionError('The object-storage runtime endpoint is not a valid HTTP or HTTPS URL.')

    product_key = str(product or '').strip().lower().replace('-', '_')
    if product_key == 'minio':
        probe_url = urlunsplit((parsed.scheme, parsed.netloc, '/minio/health/live', '', ''))
        method = 'GET'
        probe = 'minio-health-live'
    else:
        probe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', '', ''))
        method = 'HEAD'
        probe = 'endpoint-head'

    started = perf_counter()
    try:
        response = requests.request(
            method,
            probe_url,
            timeout=max(int(timeout), 1),
            verify=verify_ssl,
            allow_redirects=False,
        )
    except requests.exceptions.SSLError as exc:
        raise MinioConnectionError('TLS validation failed during the object-storage runtime health probe.') from exc
    except RequestException as exc:
        raise MinioConnectionError(
            'KAORI could not reach the object-storage endpoint during the lightweight runtime health probe.'
        ) from exc

    latency_ms = max(int((perf_counter() - started) * 1000), 0)
    if product_key == 'minio' and response.status_code != 200:
        raise MinioConnectionError(f'MinIO runtime health endpoint returned HTTP {response.status_code}.')
    if product_key != 'minio' and response.status_code >= 500:
        raise MinioConnectionError(f'Object-storage runtime endpoint returned HTTP {response.status_code}.')
    return MinioRuntimeProbeResult(
        connected=True,
        latency_ms=latency_ms,
        status_code=response.status_code,
        probe=probe,
    )


def probe_instance_runtime_health(instance: MinioInstance) -> MinioRuntimeProbeResult:
    return probe_runtime_values(
        endpoint=instance.endpoint,
        timeout=instance.timeout,
        verify_ssl=instance.verify_ssl,
        product=instance.detected_product,
    )


def _client_error_message(exc: ClientError) -> str:
    error = exc.response.get('Error') or {}
    code = str(error.get('Code') or '').strip()
    if code in {'AccessDenied', 'AllAccessDisabled'}:
        return (
            'The access key reached the S3 API, but ListBuckets was denied. '
            'KAORI requires s3:ListAllMyBuckets to validate bucket-discovery capability and run inventory jobs.'
        )
    if code in {'InvalidAccessKeyId', 'SignatureDoesNotMatch', 'InvalidToken', 'ExpiredToken'}:
        return (
            'The MinIO S3 API rejected the submitted credentials or request signature. '
            'Verify the Access Key, Secret Key, endpoint hostname, and S3 region.'
        )
    message = str(error.get('Message') or code or 'S3 request failed').strip()
    return f'MinIO S3 API returned {code or "an error"}: {message}'


def _detect_product_identity(
    *,
    endpoint: str,
    timeout: int,
    verify_ssl: bool,
    server_header: str | None,
    deployment_id: str | None,
) -> tuple[str, str]:
    normalized_header = str(server_header or '').lower()
    if 'astor' in normalized_header:
        return 'astor', 'server-header'
    evidence = _minio_identity_evidence(
        endpoint=endpoint,
        timeout=timeout,
        verify_ssl=verify_ssl,
        server_header=server_header,
        deployment_id=deployment_id,
    )
    return ('minio', evidence) if evidence != 'unverified' else ('s3_compatible', evidence)


def _minio_identity_evidence(
    *,
    endpoint: str,
    timeout: int,
    verify_ssl: bool,
    server_header: str | None,
    deployment_id: str | None,
) -> str:
    if deployment_id:
        return 'x-minio-deployment-id'
    if 'minio' in str(server_header or '').lower():
        return 'server-header'
    if _probe_minio_liveness(endpoint=endpoint, timeout=timeout, verify_ssl=verify_ssl):
        return 'health-live'
    return 'unverified'


def _probe_minio_liveness(*, endpoint: str, timeout: int, verify_ssl: bool) -> bool:
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return False
    health_url = urlunsplit((parsed.scheme, parsed.netloc, '/minio/health/live', '', ''))
    try:
        response = requests.get(
            health_url,
            timeout=max(int(timeout), 1),
            verify=verify_ssl,
            allow_redirects=False,
        )
    except RequestException:
        return False
    return response.status_code == 200


def test_instance_connection(instance: MinioInstance) -> MinioConnectionResult:
    return test_connection_values(
        endpoint=instance.endpoint,
        access_key=instance.access_key,
        secret_key=instance.secret_key,
        region=instance.region,
        addressing_style=instance.addressing_style,
        timeout=instance.timeout,
        verify_ssl=instance.verify_ssl,
    )
