from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import boto3
import requests
from botocore.auth import S3SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config as BotoCoreConfig
from botocore.credentials import Credentials
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
    """Provider-neutral inventory payload emitted by the MinIO/S3 collector.

    Identity discovery is intentionally lightweight. Provider-specific enrichers may
    populate the normalized states and provider_metadata without changing the page
    contract or Job Execution ownership.
    """

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


@dataclass(frozen=True, slots=True)
class MinioQuotaEvidence:
    quota_bytes: int | None
    state: str
    code: str
    source: str
    checked_at: datetime
    status_code: int | None = None
    provider_code: str | None = None


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
    warning_count: int = 0
    usage_stats_mode: str = 'disabled'


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


def _optional_bucket_call(
    client,
    method_name: str,
    bucket_name: str,
    *,
    not_configured_codes: set[str],
) -> tuple[dict[str, Any] | None, str | None]:
    """Return one optional bucket configuration without failing the fleet snapshot.

    Inventory identity is authoritative even when the credential cannot inspect one
    enrichment API. Missing configuration, unsupported capability, and insufficient
    permission remain distinct normalized states for presentation and governance.
    """
    try:
        payload = getattr(client, method_name)(Bucket=bucket_name)
        return payload if isinstance(payload, dict) else {}, None
    except ClientError as exc:
        code = _client_error_code(exc)
        status_code = int((exc.response.get('ResponseMetadata') or {}).get('HTTPStatusCode') or 0)
        if code in not_configured_codes:
            return None, 'not_configured'
        if code in _OPTIONAL_UNSUPPORTED_CODES or status_code == 501:
            return None, 'not_supported'
        if code in _OPTIONAL_ACCESS_DENIED_CODES:
            return None, 'not_collected'
        return None, 'not_collected'
    except (BotoCoreError, OSError):
        return None, 'not_collected'


def _principal_has_wildcard(principal: Any) -> bool:
    if principal == '*':
        return True
    if isinstance(principal, dict):
        return any(_principal_has_wildcard(value) for value in principal.values())
    if isinstance(principal, (list, tuple, set)):
        return any(_principal_has_wildcard(value) for value in principal)
    return False


def _bucket_policy_exposure(policy_text: str | None) -> str:
    if not policy_text:
        return 'private'
    try:
        policy = json.loads(policy_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 'unknown'
    statements = policy.get('Statement') or []
    if isinstance(statements, dict):
        statements = [statements]
    restricted_wildcard = False
    for statement in statements:
        if not isinstance(statement, dict) or str(statement.get('Effect') or '').lower() != 'allow':
            continue
        if not _principal_has_wildcard(statement.get('Principal')):
            continue
        if statement.get('Condition'):
            restricted_wildcard = True
            continue
        return 'public'
    return 'restricted' if restricted_wildcard else 'private'


def _minio_admin_error_code(response) -> str | None:
    """Return a sanitized MinIO/S3-style provider error code when available."""
    try:
        payload = response.json()
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict):
        for key in ('Code', 'code', 'error', 'Error'):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested = value.get('Code') or value.get('code')
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    body = str(getattr(response, 'text', '') or '')
    for marker in ('<Code>', '<code>'):
        if marker in body:
            closing = '</Code>' if marker == '<Code>' else '</code>'
            return body.split(marker, 1)[1].split(closing, 1)[0].strip() or None
    return None


def _quota_error_evidence(
    *,
    code: str,
    source: str,
    checked_at: datetime,
    status_code: int | None = None,
    provider_code: str | None = None,
    state: str = 'not_collected',
) -> MinioQuotaEvidence:
    return MinioQuotaEvidence(
        quota_bytes=None,
        state=state,
        code=code,
        source=source,
        checked_at=checked_at,
        status_code=status_code,
        provider_code=provider_code,
    )


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
    """Read MinIO bucket quota and retain operator-safe diagnostic evidence.

    MinIO quota is optional provider enrichment. Reading quota requires the
    admin:GetBucketQuota permission. Permission, routing, TLS, or Admin API failures
    are recorded on the inventory snapshot and never abort the whole Object Storage
    Inventory Sync.
    """
    checked_at = datetime.now(UTC)
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return _quota_error_evidence(
            code='invalid_endpoint',
            source='minio_admin_api_v3',
            checked_at=checked_at,
        )

    # Prefer Admin API v3 for legacy MinIO compatibility and fall forward to v4
    # only when the requested API generation is genuinely absent.
    api_versions = ('v3', 'v4')
    last_unsupported: MinioQuotaEvidence | None = None
    for api_version in api_versions:
        source = f'minio_admin_api_{api_version}'
        admin_url = urlunsplit(
            (parsed.scheme, parsed.netloc, f'/minio/admin/{api_version}/get-bucket-quota', '', '')
        )
        prepared = requests.Request('GET', admin_url, params={'bucket': bucket_name}).prepare()
        if not prepared.url:
            return _quota_error_evidence(
                code='invalid_endpoint',
                source=source,
                checked_at=checked_at,
            )

        aws_request = AWSRequest(method='GET', url=prepared.url)
        S3SigV4Auth(
            Credentials(access_key, secret_key),
            's3',
            region or 'us-east-1',
        ).add_auth(aws_request)
        headers = {str(key): str(value) for key, value in aws_request.headers.items()}

        try:
            response = requests.get(
                prepared.url,
                headers=headers,
                timeout=max(int(timeout), 1),
                verify=verify_ssl,
                allow_redirects=False,
            )
        except requests.exceptions.SSLError:
            return _quota_error_evidence(
                code='tls_validation_failed',
                source=source,
                checked_at=checked_at,
            )
        except requests.exceptions.Timeout:
            return _quota_error_evidence(
                code='admin_api_timeout',
                source=source,
                checked_at=checked_at,
            )
        except requests.exceptions.ConnectionError:
            return _quota_error_evidence(
                code='admin_api_unreachable',
                source=source,
                checked_at=checked_at,
            )
        except RequestException:
            return _quota_error_evidence(
                code='admin_api_unreachable',
                source=source,
                checked_at=checked_at,
            )

        provider_code = _minio_admin_error_code(response)
        normalized_provider_code = str(provider_code or '').strip().lower()
        status_code = int(response.status_code)

        if status_code in {404, 405, 501}:
            last_unsupported = _quota_error_evidence(
                code='not_supported',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
                provider_code=provider_code,
                state='not_supported',
            )
            continue
        if normalized_provider_code in {'signaturedoesnotmatch', 'authorizationheadermalformed'}:
            return _quota_error_evidence(
                code='signature_mismatch',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
                provider_code=provider_code,
            )
        if status_code == 401:
            return _quota_error_evidence(
                code='invalid_credentials',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
                provider_code=provider_code,
            )
        if status_code == 403:
            return _quota_error_evidence(
                code='access_denied',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
                provider_code=provider_code,
            )
        if status_code == 429:
            return _quota_error_evidence(
                code='rate_limited',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
                provider_code=provider_code,
            )
        if status_code >= 500:
            return _quota_error_evidence(
                code='provider_error',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
                provider_code=provider_code,
            )
        if not response.ok:
            return _quota_error_evidence(
                code='provider_error',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
                provider_code=provider_code,
            )

        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError):
            return _quota_error_evidence(
                code='invalid_response',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
            )
        if not isinstance(payload, dict):
            return _quota_error_evidence(
                code='invalid_response',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
            )

        # MinIO madmin BucketQuota serializes the configured ceiling as `size`.
        # Keep the historical `quota` key as a compatibility fallback.
        raw_quota = payload.get('size', payload.get('quota', 0))
        try:
            quota_bytes = int(raw_quota or 0)
        except (TypeError, ValueError):
            return _quota_error_evidence(
                code='invalid_response',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
            )
        if quota_bytes <= 0:
            return MinioQuotaEvidence(
                quota_bytes=None,
                state='not_configured',
                code='not_configured',
                source=source,
                checked_at=checked_at,
                status_code=status_code,
            )
        return MinioQuotaEvidence(
            quota_bytes=quota_bytes,
            state='configured',
            code='collected',
            source=source,
            checked_at=checked_at,
            status_code=status_code,
        )

    return last_unsupported or _quota_error_evidence(
        code='not_supported',
        source='minio_admin_api_v3',
        checked_at=checked_at,
        state='not_supported',
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
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
    timeout: int,
    verify_ssl: bool,
    collect_quota: bool,
    collect_usage_stats: bool,
) -> MinioBucketSummary:
    name = summary.name
    gaps: list[str] = []
    native_rows: list[dict[str, Any]] = []

    quota_observed_at: datetime | None = None
    if collect_quota:
        quota_evidence = _minio_admin_bucket_quota(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            bucket_name=name,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        quota_bytes = quota_evidence.quota_bytes
        quota_state = quota_evidence.state
        quota_source = quota_evidence.source
        quota_evidence_code = quota_evidence.code
        quota_checked_at = quota_evidence.checked_at
        if quota_state in {'configured', 'not_configured'}:
            quota_observed_at = quota_checked_at
        elif quota_state in {'not_collected', 'not_supported'}:
            gaps.append('Bucket Quota')
    else:
        quota_bytes = None
        quota_state = 'not_supported'
        quota_source = 'not_supported'
        quota_evidence_code = 'not_supported'
        quota_checked_at = datetime.now(UTC)
        quota_evidence = MinioQuotaEvidence(
            quota_bytes=None,
            state=quota_state,
            code=quota_evidence_code,
            source=quota_source,
            checked_at=quota_checked_at,
        )

    versioning_payload, versioning_gap = _optional_bucket_call(
        client,
        'get_bucket_versioning',
        name,
        not_configured_codes=set(),
    )
    if versioning_gap:
        versioning_state = versioning_gap
        gaps.append('Versioning')
        native_versioning = versioning_gap.replace('_', ' ').title()
    else:
        native_versioning = str((versioning_payload or {}).get('Status') or 'Not Configured')
        versioning_state = {
            'Enabled': 'enabled',
            'Suspended': 'suspended',
        }.get(native_versioning, 'not_configured')
    native_rows.append({'label': 'Versioning', 'value': native_versioning})

    encryption_payload, encryption_gap = _optional_bucket_call(
        client,
        'get_bucket_encryption',
        name,
        not_configured_codes={
            'ServerSideEncryptionConfigurationNotFoundError',
            'NoSuchServerSideEncryptionConfiguration',
        },
    )
    if encryption_gap:
        encryption_state = encryption_gap
        algorithms: list[str] = []
        if encryption_gap == 'not_collected':
            gaps.append('Encryption')
    else:
        rules = ((encryption_payload or {}).get('ServerSideEncryptionConfiguration') or {}).get('Rules') or []
        algorithms = sorted(
            {
                str((rule.get('ApplyServerSideEncryptionByDefault') or {}).get('SSEAlgorithm') or '').strip()
                for rule in rules
                if str((rule.get('ApplyServerSideEncryptionByDefault') or {}).get('SSEAlgorithm') or '').strip()
            }
        )
        encryption_state = 'configured' if rules else 'not_configured'
    native_rows.append(
        {
            'label': 'Encryption',
            'value': ', '.join(algorithms) if algorithms else encryption_state.replace('_', ' ').title(),
        }
    )

    lock_payload, lock_gap = _optional_bucket_call(
        client,
        'get_object_lock_configuration',
        name,
        not_configured_codes={'ObjectLockConfigurationNotFoundError', 'NoSuchObjectLockConfiguration'},
    )
    if lock_gap:
        immutability_state = lock_gap
        lock_value = lock_gap.replace('_', ' ').title()
        if lock_gap == 'not_collected':
            gaps.append('Immutability')
    else:
        lock_config = (lock_payload or {}).get('ObjectLockConfiguration') or {}
        immutability_state = 'enabled' if lock_config.get('ObjectLockEnabled') == 'Enabled' else 'not_configured'
        default_retention = ((lock_config.get('Rule') or {}).get('DefaultRetention') or {})
        lock_value = 'Enabled' if immutability_state == 'enabled' else 'Not Configured'
        if default_retention:
            retention_parts = [
                str(default_retention.get('Mode') or '').strip(),
                f"{default_retention.get('Days')} Days" if default_retention.get('Days') else '',
                f"{default_retention.get('Years')} Years" if default_retention.get('Years') else '',
            ]
            retention_label = ' · '.join(part for part in retention_parts if part)
            if retention_label:
                lock_value = f'{lock_value} · {retention_label}'
    native_rows.append({'label': 'Object Lock', 'value': lock_value})

    lifecycle_payload, lifecycle_gap = _optional_bucket_call(
        client,
        'get_bucket_lifecycle_configuration',
        name,
        not_configured_codes={'NoSuchLifecycleConfiguration'},
    )
    lifecycle_rules = (lifecycle_payload or {}).get('Rules') or []
    lifecycle_state = lifecycle_gap or ('configured' if lifecycle_rules else 'not_configured')
    if lifecycle_gap == 'not_collected':
        gaps.append('Lifecycle')
    native_rows.append({'label': 'Lifecycle Rules', 'value': len(lifecycle_rules)})

    replication_payload, replication_gap = _optional_bucket_call(
        client,
        'get_bucket_replication',
        name,
        not_configured_codes={'ReplicationConfigurationNotFoundError', 'NoSuchReplicationConfiguration'},
    )
    replication_config = (replication_payload or {}).get('ReplicationConfiguration') or {}
    replication_rules = replication_config.get('Rules') or []
    replication_state = replication_gap or ('configured' if replication_rules else 'not_configured')
    if replication_gap == 'not_collected':
        gaps.append('Replication')
    native_rows.append({'label': 'Replication Rules', 'value': len(replication_rules)})

    policy_payload, policy_gap = _optional_bucket_call(
        client,
        'get_bucket_policy',
        name,
        not_configured_codes={'NoSuchBucketPolicy'},
    )
    if policy_gap:
        access_policy_state = policy_gap
        exposure_state = 'private' if policy_gap == 'not_configured' else policy_gap
        policy_value = policy_gap.replace('_', ' ').title()
        if policy_gap == 'not_collected':
            gaps.append('Access Policy')
    else:
        policy_text = str((policy_payload or {}).get('Policy') or '').strip()
        access_policy_state = 'configured' if policy_text else 'not_configured'
        exposure_state = _bucket_policy_exposure(policy_text)
        policy_value = 'Configured' if policy_text else 'Not Configured'
    native_rows.append({'label': 'Bucket Policy', 'value': policy_value})
    native_rows.append({'label': 'Policy Exposure', 'value': exposure_state.replace('_', ' ').title()})

    size_bytes: int | None = None
    object_count: int | None = None
    usage_state = 'disabled'
    usage_observed_at: datetime | None = None
    if collect_usage_stats:
        usage_state = 'not_collected'
        try:
            size_bytes, object_count = _collect_bucket_usage_stats(client, name)
            usage_state = 'collected'
            usage_observed_at = datetime.now(UTC)
        except (ClientError, BotoCoreError, OSError):
            gaps.append('Usage Statistics')
    provider_metadata: dict[str, Any] = {
        'enrichment_profile': 'minio-s3-bucket-v1',
        'enrichment_profile_label': 'MinIO S3 Bucket v1',
        'quota_collection': quota_source,
        'quota_evidence': {
            'code': quota_evidence.code,
            'status_code': quota_evidence.status_code,
            'provider_code': quota_evidence.provider_code,
        },
        'usage_stats_mode': 'full_scan' if collect_usage_stats else 'disabled',
        'sections': [
            {
                'title': 'MinIO Bucket Configuration',
                'description': 'Provider-native S3 configuration evidence collected by Object Storage Inventory Sync.',
                'icon': 'settings-2',
                'rows': native_rows,
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
        versioning_state=versioning_state,
        immutability_state=immutability_state,
        encryption_state=encryption_state,
        lifecycle_state=lifecycle_state,
        replication_state=replication_state,
        access_policy_state=access_policy_state,
        exposure_state=exposure_state,
        provider_metadata=provider_metadata,
        quota_bytes=quota_bytes,
        quota_state=quota_state,
        quota_source=quota_source,
        quota_evidence_code=quota_evidence_code,
        quota_checked_at=quota_checked_at,
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
    collect_quota: bool = True,
    collect_usage_stats: bool = False,
) -> MinioInventoryResult:
    """Collect and enrich bucket inventory without mutating provider validation state."""
    started = perf_counter()
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
    base_buckets = _bucket_inventory(payload, location=region)
    buckets = tuple(
        _enrich_bucket_summary(
            client,
            summary,
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            timeout=timeout,
            verify_ssl=verify_ssl,
            collect_quota=collect_quota,
            collect_usage_stats=collect_usage_stats,
        )
        for summary in base_buckets
    )
    warning_count = sum(
        len(bucket.provider_metadata.get('enrichment_gaps') or ())
        for bucket in buckets
    )
    total_latency_ms = max(int((perf_counter() - started) * 1000), list_latency_ms)
    return MinioInventoryResult(
        latency_ms=total_latency_ms,
        buckets=buckets,
        warning_count=warning_count,
        usage_stats_mode='full_scan' if collect_usage_stats else 'disabled',
    )


def collect_instance_bucket_inventory(
    instance: MinioInstance,
    *,
    collect_usage_stats: bool = False,
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
        raise MinioConnectionError(
            'TLS validation failed during the object-storage runtime health probe.'
        ) from exc
    except RequestException as exc:
        raise MinioConnectionError(
            'KAORI could not reach the object-storage endpoint during the lightweight runtime health probe.'
        ) from exc

    latency_ms = max(int((perf_counter() - started) * 1000), 0)
    if product_key == 'minio' and response.status_code != 200:
        raise MinioConnectionError(
            f'MinIO runtime health endpoint returned HTTP {response.status_code}.'
        )
    if product_key != 'minio' and response.status_code >= 500:
        raise MinioConnectionError(
            f'Object-storage runtime endpoint returned HTTP {response.status_code}.'
        )
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
