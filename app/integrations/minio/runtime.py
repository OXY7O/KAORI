from __future__ import annotations

from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import requests
from requests import RequestException

from app.integrations.minio.contracts import MinioConnectionError, MinioRuntimeProbeResult


def probe_runtime_values(
    *,
    endpoint: str,
    timeout: int = 5,
    verify_ssl: bool = True,
    product: str | None = None,
) -> MinioRuntimeProbeResult:
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise MinioConnectionError('The object-storage runtime endpoint is not a valid HTTP or HTTPS URL.')

    product_key = str(product or '').strip().lower().replace('-', '_')
    if product_key == 'minio':
        probe_url = urlunsplit((parsed.scheme, parsed.netloc, '/minio/health/live', '', ''))
        method, probe = 'GET', 'minio-health-live'
    else:
        probe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', '', ''))
        method, probe = 'HEAD', 'endpoint-head'

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
