from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Unpack
from urllib.parse import urlsplit, urlunsplit

import requests
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
from requests import RequestException

from app.integrations.storage.object_storage.adapters.s3 import (
    S3TransportFailure,
    build_s3_client,
)
from app.integrations.storage.object_storage.adapters.s3 import (
    list_buckets as list_s3_buckets,
)
from app.integrations.storage.object_storage.providers.minio.contracts import (
    MinioConnectionError,
    MinioConnectionResult,
    MinioInventoryConnection,
    MinioInventoryOptions,
    MinioInventoryResult,
    MinioQuotaEvidence,
    MinioRuntimeProbeResult,
    MinioUsageEvidence,
)
from app.models.minio import MinioInstance

InventoryProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True, slots=True)
class MinioBucketSummary:
    """Provider-neutral inventory payload emitted by the MinIO/S3 collector."""

    name: str
    creation_date: datetime | None
    native_type: str = 'bucket'
    location: str | None = None
    versioning_state: str = 'not_collected'
    immutability_state: str = 'not_collected'
    encryption_state: str = 'not_collected'
    lifecycle_state: str = 'not_collected'
    replication_state: str = 'not_collected'
    access_policy_state: str = 'not_collected'
    exposure_state: str = 'not_collected'
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    quota_bytes: int | None = None
    quota_state: str = 'not_collected'
    quota_source: str | None = None
    quota_evidence_code: str = 'not_collected'
    quota_checked_at: datetime | None = None
    quota_observed_at: datetime | None = None
    size_bytes: int | None = None
    object_count: int | None = None
    usage_state: str = 'not_collected'
    usage_observed_at: datetime | None = None


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
    try:
        return list_s3_buckets(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            addressing_style=addressing_style,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
    except S3TransportFailure as exc:
        if exc.kind == 'api':
            code = str(exc.code or '').strip()
            if code in {'AccessDenied', 'AllAccessDisabled'}:
                message = (
                    'The access key reached the S3 API, but ListBuckets was denied. '
                    'KAORI requires s3:ListAllMyBuckets to validate bucket-discovery capability and run inventory jobs.'
                )
            elif code in {'InvalidAccessKeyId', 'SignatureDoesNotMatch', 'InvalidToken', 'ExpiredToken'}:
                message = (
                    'The MinIO S3 API rejected the submitted credentials or request signature. '
                    'Verify the Access Key, Secret Key, endpoint hostname, and S3 region.'
                )
            else:
                message = f'MinIO S3 API returned {code or "an error"}: {exc.message}'
        elif exc.kind == 'connection':
            message = 'KAORI could not reach the MinIO S3 API endpoint. Verify the API URL, port, network route, and proxy settings.'
        elif exc.kind == 'tls':
            message = 'TLS validation failed for the MinIO S3 API endpoint. Verify the certificate chain or disable TLS verification only for an approved internal exception.'
        else:
            message = f'MinIO S3 API validation failed: {exc.message}'
        raise MinioConnectionError(message) from exc


def _bucket_inventory(
    payload: dict[str, Any],
    *,
    location: str | None = None,
) -> tuple[MinioBucketSummary, ...]:
    return tuple(
        sorted(
            (
                MinioBucketSummary(
                    name=str(item.get('Name') or '').strip(),
                    creation_date=item.get('CreationDate') if isinstance(item.get('CreationDate'), datetime) else None,
                    native_type='bucket',
                    location=location or None,
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
    bucket_inventory = _bucket_inventory(payload, location=region)
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


_OPTIONAL_ACCESS_DENIED_CODES = {'AccessDenied', 'AllAccessDisabled'}
_OPTIONAL_UNSUPPORTED_CODES = {'NotImplemented', 'NotSupported', 'MethodNotAllowed', 'XNotImplemented'}


def _client_error_code(exc: ClientError) -> str:
    return str((exc.response.get('Error') or {}).get('Code') or '').strip()


def _bucket_policy_exposure(policy_text: str | None) -> str:
    from app.integrations.storage.object_storage.providers.minio.bucket_enrichment import bucket_policy_exposure

    return bucket_policy_exposure(policy_text)


_MINIO_QUOTA_EVIDENCE_CODES = frozenset(
    {
        'collected',
        'not_configured',
        'access_denied',
        'signature_mismatch',
        'invalid_credentials',
        'admin_api_unreachable',
        'admin_api_timeout',
        'tls_validation_failed',
        'rate_limited',
        'invalid_response',
        'provider_error',
        'not_supported',
        'invalid_endpoint',
    }
)


def _minio_quota_api_versions() -> tuple[str, str]:
    api_versions = ('v3', 'v4')
    return api_versions


def _minio_quota_path(api_version: str) -> str:
    return f'/minio/admin/{api_version}/get-bucket-quota'


def _parse_minio_quota_payload(payload: dict[str, Any]) -> tuple[int | None, bool]:
    parsed_quota_values: list[tuple[str, int]] = []
    invalid_quota_value = False
    for field_name in ('size', 'quota'):
        if field_name not in payload:
            continue
        try:
            value = int(payload.get(field_name) or 0)
        except (TypeError, ValueError):
            invalid_quota_value = True
            continue
        parsed_quota_values.append((field_name, value))
    quota_bytes = next((value for field_name, value in parsed_quota_values if field_name == 'size' and value > 0), 0)
    if quota_bytes <= 0:
        quota_bytes = next(
            (value for field_name, value in parsed_quota_values if field_name == 'quota' and value > 0), 0
        )
    invalid_payload = bool(not parsed_quota_values and invalid_quota_value)
    return (quota_bytes if quota_bytes > 0 else None), invalid_payload


def _minio_admin_bucket_quota(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
    bucket_name: str,
    timeout: int,
    verify_ssl: bool,
) -> MinioQuotaEvidence:
    """Collect optional MinIO quota evidence; requires admin:GetBucketQuota."""
    from app.integrations.storage.object_storage.providers.minio.admin import (
        MinioQuotaCollectorHooks,
        collect_bucket_quota,
    )

    evidence = collect_bucket_quota(
        hooks=MinioQuotaCollectorHooks(
            request_get=requests.get,
            api_versions=_minio_quota_api_versions,
            quota_path=_minio_quota_path,
            parse_payload=_parse_minio_quota_payload,
        ),
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        bucket_name=bucket_name,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    if evidence.code not in _MINIO_QUOTA_EVIDENCE_CODES:
        return MinioQuotaEvidence(
            quota_bytes=None,
            state='not_collected',
            code='provider_error',
            source=evidence.source,
            checked_at=evidence.checked_at,
            status_code=evidence.status_code,
            provider_code=evidence.provider_code,
        )
    return evidence


def _usage_error_evidence(
    *,
    code: str,
    source: str,
    checked_at: datetime,
    status_code: int | None = None,
    provider_code: str | None = None,
    state: str = 'not_collected',
) -> MinioUsageEvidence:
    return MinioUsageEvidence(
        buckets={},
        state=state,
        code=code,
        source=source,
        checked_at=checked_at,
        status_code=status_code,
        provider_code=provider_code,
    )


def _parse_minio_timestamp(value: object) -> datetime | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _coerce_non_negative_usage_counter(value: object) -> int | None:
    """Normalize provider usage counters without relying on untyped JSON values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        parsed = int(value)
        return parsed if parsed >= 0 else None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = int(raw)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _minio_admin_data_usage(
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
    timeout: int,
    verify_ssl: bool,
) -> MinioUsageEvidence:
    """Read one provider-aggregated per-bucket usage snapshot without a full S3 scan."""
    from app.integrations.storage.object_storage.providers.minio.admin import signed_admin_get, usage_response_error

    checked_at = datetime.now(UTC)
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return _usage_error_evidence(code='invalid_endpoint', source='minio_admin_data_usage_v3', checked_at=checked_at)

    last_unsupported: MinioUsageEvidence | None = None
    for api_version in ('v3', 'v4'):
        source = f'minio_admin_data_usage_{api_version}'
        admin_url = urlunsplit((parsed.scheme, parsed.netloc, f'/minio/admin/{api_version}/datausageinfo', '', ''))
        response, request_error = signed_admin_get(
            request_get=requests.get,
            url=admin_url,
            params={'capacity': 'true'},
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        if request_error:
            return _usage_error_evidence(code=request_error, source=source, checked_at=checked_at)
        assert response is not None
        response_error = usage_response_error(response, source=source, checked_at=checked_at)
        if response_error is not None:
            if response_error.state == 'not_supported':
                last_unsupported = response_error
                continue
            return response_error

        status_code = int(response.status_code)
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict):
            return _usage_error_evidence(
                code='invalid_response', source=source, checked_at=checked_at, status_code=status_code
            )

        buckets_usage = payload.get('bucketsUsageInfo')
        if not isinstance(buckets_usage, dict):
            buckets_usage = {}
        normalized: dict[str, tuple[int, int]] = {}
        for bucket_name, raw_usage in buckets_usage.items():
            if not isinstance(raw_usage, dict):
                continue
            if 'size' not in raw_usage or 'objectsCount' not in raw_usage:
                continue
            size_bytes = _coerce_non_negative_usage_counter(raw_usage.get('size'))
            object_count = _coerce_non_negative_usage_counter(raw_usage.get('objectsCount'))
            if size_bytes is None or object_count is None:
                continue
            normalized[str(bucket_name)] = (size_bytes, object_count)

        return MinioUsageEvidence(
            buckets=normalized,
            state='collected',
            code='collected',
            source=source,
            checked_at=checked_at,
            observed_at=_parse_minio_timestamp(payload.get('lastUpdate')),
            status_code=status_code,
        )

    return last_unsupported or _usage_error_evidence(
        code='not_supported', source='minio_admin_data_usage_v3', checked_at=checked_at, state='not_supported'
    )


def _collect_bucket_usage_stats(client, bucket_name: str) -> tuple[int, int]:
    """Return logical bytes and current object count by scanning ListObjectsV2.

    This is intentionally opt-in because standard S3 does not expose an O(1) bucket
    usage counter. Version history and incomplete multipart uploads are not included.
    """
    size_bytes = 0
    object_count = 0
    paginator = client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name, PaginationConfig={'PageSize': 1000}):
        for item in page.get('Contents') or []:
            object_count += 1
            size_bytes += int(item.get('Size') or 0)
    return size_bytes, object_count


def _enrich_bucket_summary(
    client,
    summary: MinioBucketSummary,
    *,
    connection: MinioInventoryConnection,
    collect_quota: bool,
    usage_stats_mode: str,
    provider_usage: MinioUsageEvidence | None,
) -> MinioBucketSummary:
    """Normalize MinIO Bucket Configuration evidence.

    Uses get_bucket_versioning, get_bucket_encryption, get_object_lock_configuration,
    get_bucket_lifecycle_configuration, get_bucket_replication, and get_bucket_policy.
    """
    from app.integrations.storage.object_storage.providers.minio.bucket_enrichment import collect_bucket_configuration

    name = summary.name
    configuration = collect_bucket_configuration(client, name)
    gaps = list(configuration.gaps)

    if collect_quota:
        quota_evidence = _minio_admin_bucket_quota(
            endpoint=connection.endpoint,
            access_key=connection.access_key,
            secret_key=connection.secret_key,
            region=connection.region,
            bucket_name=name,
            timeout=connection.timeout,
            verify_ssl=connection.verify_ssl,
        )
    else:
        quota_evidence = MinioQuotaEvidence(
            quota_bytes=None,
            state='not_supported',
            code='not_supported',
            source='not_supported',
            checked_at=datetime.now(UTC),
        )
    quota_observed_at = quota_evidence.checked_at if quota_evidence.state in {'configured', 'not_configured'} else None
    if quota_evidence.state in {'not_collected', 'not_supported'} and collect_quota:
        gaps.append('Bucket Quota')

    size_bytes: int | None = None
    object_count: int | None = None
    usage_state = 'disabled'
    usage_observed_at: datetime | None = None
    usage_collection = 'disabled'
    usage_evidence: dict[str, Any] = {'code': 'disabled', 'status_code': None, 'provider_code': None}
    if usage_stats_mode == 'provider_metrics':
        usage_state = 'not_collected'
        usage_collection = provider_usage.source if provider_usage is not None else 'minio_admin_data_usage_v3'
        if provider_usage is not None:
            usage_evidence = {
                'code': provider_usage.code,
                'status_code': provider_usage.status_code,
                'provider_code': provider_usage.provider_code,
            }
            bucket_usage = provider_usage.buckets.get(name)
            if provider_usage.state == 'collected' and bucket_usage is not None:
                size_bytes, object_count = bucket_usage
                usage_state = 'collected'
                usage_observed_at = provider_usage.observed_at or provider_usage.checked_at
    elif usage_stats_mode == 'full_scan':
        usage_state = 'not_collected'
        usage_collection = 's3_list_objects_v2'
        usage_evidence = {'code': 'not_collected', 'status_code': None, 'provider_code': None}
        try:
            size_bytes, object_count = _collect_bucket_usage_stats(client, name)
            usage_state = 'collected'
            usage_observed_at = datetime.now(UTC)
            usage_evidence['code'] = 'collected'
        except (ClientError, BotoCoreError, OSError):
            gaps.append('Usage Statistics')

    provider_metadata: dict[str, Any] = {
        'enrichment_profile': 'minio-s3-bucket-v1',
        'enrichment_profile_label': 'MinIO S3 Bucket v1',
        'quota_collection': quota_evidence.source,
        'quota_evidence': {
            'code': quota_evidence.code,
            'status_code': quota_evidence.status_code,
            'provider_code': quota_evidence.provider_code,
        },
        'usage_stats_mode': usage_stats_mode,
        'usage_collection': usage_collection,
        'usage_evidence': usage_evidence,
        'sections': [
            {
                'title': 'MinIO Bucket Configuration',
                'description': 'Provider-native S3 configuration evidence collected by Object Storage Inventory Sync.',
                'icon': 'settings-2',
                'rows': configuration.native_rows,
            }
        ],
    }
    if gaps:
        provider_metadata['enrichment_gaps'] = sorted(set(gaps))

    return MinioBucketSummary(
        name=summary.name,
        creation_date=summary.creation_date,
        native_type=summary.native_type,
        location=summary.location,
        versioning_state=configuration.versioning_state,
        immutability_state=configuration.immutability_state,
        encryption_state=configuration.encryption_state,
        lifecycle_state=configuration.lifecycle_state,
        replication_state=configuration.replication_state,
        access_policy_state=configuration.access_policy_state,
        exposure_state=configuration.exposure_state,
        provider_metadata=provider_metadata,
        quota_bytes=quota_evidence.quota_bytes,
        quota_state=quota_evidence.state,
        quota_source=quota_evidence.source,
        quota_evidence_code=quota_evidence.code,
        quota_checked_at=quota_evidence.checked_at,
        quota_observed_at=quota_observed_at,
        size_bytes=size_bytes,
        object_count=object_count,
        usage_state=usage_state,
        usage_observed_at=usage_observed_at,
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
    **options: Unpack[MinioInventoryOptions],
) -> MinioInventoryResult:
    """Collect and enrich bucket inventory without mutating provider validation state."""
    started = perf_counter()
    collect_quota: bool = True
    collect_usage_stats: bool = False
    collect_quota = options.get('collect_quota', collect_quota)
    collect_usage_stats = options.get('collect_usage_stats', collect_usage_stats)
    usage_stats_mode = options.get('usage_stats_mode')
    progress_callback = options.get('progress_callback')
    resolved_usage_mode = str(usage_stats_mode or ('full_scan' if collect_usage_stats else 'disabled')).strip().lower()
    if resolved_usage_mode not in {'disabled', 'provider_metrics', 'full_scan'}:
        resolved_usage_mode = 'disabled'
    payload, list_latency_ms = _list_buckets_values(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        addressing_style=addressing_style,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    client = build_s3_client(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        addressing_style=addressing_style,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    connection = MinioInventoryConnection(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
    base_buckets = _bucket_inventory(payload, location=region)
    provider_usage: MinioUsageEvidence | None = None
    if resolved_usage_mode == 'provider_metrics':
        provider_usage = _minio_admin_data_usage(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
    total_buckets = len(base_buckets)
    enriched_buckets: list[MinioBucketSummary] = []
    for index, summary in enumerate(base_buckets, start=1):
        if progress_callback is not None:
            progress_callback(index - 1, total_buckets, summary.name)
        enriched_buckets.append(
            _enrich_bucket_summary(
                client,
                summary,
                connection=connection,
                collect_quota=collect_quota,
                usage_stats_mode=resolved_usage_mode,
                provider_usage=provider_usage,
            )
        )
        if progress_callback is not None:
            progress_callback(index, total_buckets, summary.name)
    buckets = tuple(enriched_buckets)
    warning_count = sum(len(bucket.provider_metadata.get('enrichment_gaps') or ()) for bucket in buckets)
    total_latency_ms = max(int((perf_counter() - started) * 1000), list_latency_ms)
    return MinioInventoryResult(
        latency_ms=total_latency_ms,
        buckets=buckets,
        warning_count=warning_count,
        usage_stats_mode=resolved_usage_mode,
    )


def collect_instance_bucket_inventory(
    instance: MinioInstance,
    *,
    collect_usage_stats: bool = False,
    usage_stats_mode: str | None = None,
    progress_callback: InventoryProgressCallback | None = None,
) -> MinioInventoryResult:
    provider_key = str(instance.detected_product or '').strip().lower().replace('-', '_')
    return collect_bucket_inventory_values(
        endpoint=instance.endpoint,
        access_key=instance.access_key,
        secret_key=instance.secret_key,
        region=instance.region,
        addressing_style=instance.addressing_style,
        timeout=instance.timeout,
        verify_ssl=instance.verify_ssl,
        collect_quota=provider_key == 'minio',
        collect_usage_stats=collect_usage_stats,
        usage_stats_mode=usage_stats_mode,
        progress_callback=progress_callback,
    )


def probe_runtime_values(
    *, endpoint: str, timeout: int = 5, verify_ssl: bool = True, product: str | None = None
) -> MinioRuntimeProbeResult:
    """Run a lightweight provider health probe without collecting inventory."""
    from app.integrations.storage.object_storage.providers.minio.runtime import probe_runtime_values as probe

    return probe(endpoint=endpoint, timeout=timeout, verify_ssl=verify_ssl, product=product)


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
        response = requests.get(  # nosec B113 - timeout is bounded to at least one second.
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
