from __future__ import annotations

from dataclasses import dataclass
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
class MinioConnectionResult:
    connected: bool
    latency_ms: int
    bucket_count: int
    bucket_names: tuple[str, ...]
    server_header: str | None
    deployment_id: str | None
    product: str
    identity_evidence: str


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
    buckets = tuple(
        sorted(
            str(item.get('Name') or '').strip()
            for item in payload.get('Buckets') or []
            if str(item.get('Name') or '').strip()
        )
    )
    return MinioConnectionResult(
        connected=True,
        latency_ms=latency_ms,
        bucket_count=len(buckets),
        bucket_names=buckets,
        server_header=server_header,
        deployment_id=deployment_id,
        product=product,
        identity_evidence=identity_evidence,
    )


def _client_error_message(exc: ClientError) -> str:
    error = exc.response.get('Error') or {}
    code = str(error.get('Code') or '').strip()
    if code in {'AccessDenied', 'AllAccessDisabled'}:
        return (
            'The access key reached the S3 API, but ListBuckets was denied. '
            'KAORI requires s3:ListAllMyBuckets to discover object-storage assets.'
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
