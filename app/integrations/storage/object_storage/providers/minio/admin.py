from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from botocore.auth import S3SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from requests import Response

from app.integrations.storage.object_storage.providers.minio.contracts import MinioQuotaEvidence, MinioUsageEvidence

RequestGet = Callable[..., Response]
QuotaApiVersions = Callable[[], tuple[str, str]]
QuotaPath = Callable[[str], str]
QuotaPayloadParser = Callable[[dict[str, Any]], tuple[int | None, bool]]


@dataclass(frozen=True, slots=True)
class MinioQuotaCollectorHooks:
    request_get: RequestGet
    api_versions: QuotaApiVersions
    quota_path: QuotaPath
    parse_payload: QuotaPayloadParser


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


def _admin_error_code(response: Response) -> str | None:
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


def _signed_admin_get(
    *,
    request_get: RequestGet,
    url: str,
    params: dict[str, str],
    access_key: str,
    secret_key: str,
    region: str,
    timeout: int,
    verify_ssl: bool,
) -> tuple[Response | None, str | None]:
    prepared = requests.Request('GET', url, params=params).prepare()
    if not prepared.url:
        return None, 'invalid_endpoint'
    aws_request = AWSRequest(method='GET', url=prepared.url)
    S3SigV4Auth(Credentials(access_key, secret_key), 's3', region or 'us-east-1').add_auth(aws_request)
    headers = {str(key): str(value) for key, value in aws_request.headers.items()}
    try:
        response = request_get(
            prepared.url,
            headers=headers,
            timeout=max(int(timeout), 1),
            verify=verify_ssl,
            allow_redirects=False,
        )
    except requests.exceptions.SSLError:
        return None, 'tls_validation_failed'
    except requests.exceptions.Timeout:
        return None, 'admin_api_timeout'
    except (requests.exceptions.ConnectionError, requests.RequestException):
        return None, 'admin_api_unreachable'
    return response, None


def _quota_http_error(
    response: Response,
    *,
    source: str,
    checked_at: datetime,
) -> MinioQuotaEvidence | None:
    provider_code = _admin_error_code(response)
    normalized = str(provider_code or '').strip().lower()
    status_code = int(response.status_code)
    if status_code in {404, 405, 501}:
        return _quota_error_evidence(
            code='not_supported',
            source=source,
            checked_at=checked_at,
            status_code=status_code,
            provider_code=provider_code,
            state='not_supported',
        )
    if normalized in {'signaturedoesnotmatch', 'authorizationheadermalformed'}:
        code = 'signature_mismatch'
    elif status_code == 401:
        code = 'invalid_credentials'
    elif status_code == 403:
        code = 'access_denied'
    elif status_code == 429:
        code = 'rate_limited'
    elif status_code >= 500 or not response.ok:
        code = 'provider_error'
    else:
        return None
    return _quota_error_evidence(
        code=code,
        source=source,
        checked_at=checked_at,
        status_code=status_code,
        provider_code=provider_code,
    )


def collect_bucket_quota(
    *,
    hooks: MinioQuotaCollectorHooks,
    endpoint: str,
    access_key: str,
    secret_key: str,
    region: str,
    bucket_name: str,
    timeout: int,
    verify_ssl: bool,
) -> MinioQuotaEvidence:
    checked_at = datetime.now(UTC)
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return _quota_error_evidence(code='invalid_endpoint', source='minio_admin_api_v3', checked_at=checked_at)

    last_unsupported: MinioQuotaEvidence | None = None
    for api_version in hooks.api_versions():
        source = f'minio_admin_api_{api_version}'
        admin_url = urlunsplit((parsed.scheme, parsed.netloc, hooks.quota_path(api_version), '', ''))
        response, request_error = _signed_admin_get(
            request_get=hooks.request_get,
            url=admin_url,
            params={'bucket': bucket_name},
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        if request_error:
            return _quota_error_evidence(code=request_error, source=source, checked_at=checked_at)
        assert response is not None
        http_error = _quota_http_error(response, source=source, checked_at=checked_at)
        if http_error is not None:
            if http_error.state == 'not_supported':
                last_unsupported = http_error
                continue
            return http_error
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict):
            return _quota_error_evidence(
                code='invalid_response', source=source, checked_at=checked_at, status_code=int(response.status_code)
            )
        quota_bytes, invalid_payload = hooks.parse_payload(payload)
        if invalid_payload:
            return _quota_error_evidence(
                code='invalid_response', source=source, checked_at=checked_at, status_code=int(response.status_code)
            )
        if quota_bytes is None:
            return MinioQuotaEvidence(
                quota_bytes=None,
                state='not_configured',
                code='not_configured',
                source=source,
                checked_at=checked_at,
                status_code=int(response.status_code),
            )
        return MinioQuotaEvidence(
            quota_bytes=quota_bytes,
            state='configured',
            code='collected',
            source=source,
            checked_at=checked_at,
            status_code=int(response.status_code),
        )

    return last_unsupported or _quota_error_evidence(
        code='not_supported', source='minio_admin_api_v3', checked_at=checked_at, state='not_supported'
    )


# Shared request/status helpers used by the provider-metrics collector in client.py.
def signed_admin_get(
    *,
    request_get: RequestGet,
    url: str,
    params: dict[str, str],
    access_key: str,
    secret_key: str,
    region: str,
    timeout: int,
    verify_ssl: bool,
) -> tuple[Response | None, str | None]:
    return _signed_admin_get(
        request_get=request_get,
        url=url,
        params=params,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )


def usage_response_error(response: Response, *, source: str, checked_at: datetime) -> MinioUsageEvidence | None:
    provider_code = _admin_error_code(response)
    normalized = str(provider_code or '').strip().lower()
    status_code = int(response.status_code)
    if status_code in {404, 405, 501}:
        code, state = 'not_supported', 'not_supported'
    elif normalized in {'signaturedoesnotmatch', 'authorizationheadermalformed'}:
        code, state = 'signature_mismatch', 'not_collected'
    elif status_code == 401:
        code, state = 'invalid_credentials', 'not_collected'
    elif status_code == 403:
        code, state = 'access_denied', 'not_collected'
    elif status_code == 429:
        code, state = 'rate_limited', 'not_collected'
    elif status_code >= 500 or not response.ok:
        code, state = 'provider_error', 'not_collected'
    else:
        return None
    return MinioUsageEvidence(
        buckets={},
        state=state,
        code=code,
        source=source,
        checked_at=checked_at,
        status_code=status_code,
        provider_code=provider_code,
    )
