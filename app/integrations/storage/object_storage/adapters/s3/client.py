from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

import boto3
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

S3FailureKind = Literal['api', 'connection', 'tls', 'transport']


@dataclass(frozen=True, slots=True)
class S3TransportFailure(RuntimeError):
    kind: S3FailureKind
    message: str
    code: str | None = None

    def __str__(self) -> str:
        return self.message


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
    """Build the shared S3 transport used by S3-compatible providers."""

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


def list_buckets(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
    addressing_style: str,
    timeout: int,
    verify_ssl: bool,
) -> tuple[dict[str, Any], int]:
    """Validate S3 transport and return the raw ListBuckets payload plus latency."""

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
        error = exc.response.get('Error') or {}
        code = str(error.get('Code') or '').strip() or None
        message = str(error.get('Message') or code or 'S3 request failed').strip()
        raise S3TransportFailure('api', message, code) from exc
    except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, ProxyConnectionError) as exc:
        raise S3TransportFailure('connection', 'The S3 API endpoint is unreachable.') from exc
    except SSLError as exc:
        raise S3TransportFailure('tls', 'TLS validation failed for the S3 API endpoint.') from exc
    except (BotoCoreError, OSError) as exc:
        raise S3TransportFailure('transport', str(exc) or 'S3 transport validation failed.') from exc
    latency_ms = max(int((perf_counter() - started) * 1000), 0)
    return payload, latency_ms
