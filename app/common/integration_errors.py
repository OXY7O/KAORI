from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__

    return chain


def _exception_names(chain: list[BaseException]) -> set[str]:
    return {type(item).__name__ for item in chain}


def _combined_message(chain: list[BaseException]) -> str:
    return ' '.join(str(item) for item in chain if str(item)).lower()


def _endpoint_context(
    endpoint: str | None,
    request_path: str | None,
) -> dict[str, str]:
    normalized_endpoint = (endpoint or '').strip()
    parsed = urlparse(normalized_endpoint)

    scheme = parsed.scheme or 'http'
    hostname = parsed.hostname or normalized_endpoint or 'the configured endpoint'
    port = parsed.port
    default_port = 443 if scheme == 'https' else 80
    display_port = port or default_port
    target = f'{hostname}:{display_port}'
    path = request_path or parsed.path or '/'

    return {
        'scheme': scheme,
        'hostname': hostname,
        'port': str(display_port),
        'target': target,
        'path': path,
    }


def _http_status(chain: list[BaseException]) -> int | None:
    for item in chain:
        status = getattr(item, 'status', None)
        if isinstance(status, int) and 100 <= status <= 599:
            return status

    message = ' '.join(str(item) for item in chain if str(item))
    patterns = (
        r'(?:http|status)\s*[:=]?\s*(\d{3})',
        r'^\s*\((\d{3})\)',
    )

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
        if match is not None:
            return int(match.group(1))

    return None


def describe_integration_failure(
    exc: BaseException,
    *,
    service_name: str,
    endpoint: str | None,
    request_path: str | None = None,
    timeout_seconds: int | float | None = None,
) -> dict[str, Any]:
    """Convert low-level HTTP exceptions into user-facing operational context.

    The raw exception chain remains available to application logs through normal
    exception logging, while notifications and UI feedback receive concise,
    actionable wording.
    """
    chain = _exception_chain(exc)
    names = _exception_names(chain)
    message = _combined_message(chain)
    endpoint_context = _endpoint_context(endpoint, request_path)
    timeout_label = f'{timeout_seconds:g} seconds' if timeout_seconds is not None else 'the configured timeout'
    service = service_name.strip() or 'the integration'
    target = endpoint_context['target']
    path = endpoint_context['path']
    scheme = endpoint_context['scheme'].upper()

    result: dict[str, Any] = {
        'code': 'connection_failed',
        'reason': 'Connection failed',
        'detail': (
            f'KAORI could not complete the {service} connection test for {target}. '
            f'Verify the endpoint, network reachability, authentication, and TLS settings before retrying.'
        ),
        'endpoint_host': endpoint_context['hostname'],
        'endpoint_port': endpoint_context['port'],
        'request_path': path,
    }

    if (
        {'ConnectTimeout', 'ReadTimeout', 'Timeout'} & names
        or 'timed out' in message
        or 'connection timeout' in message
    ):
        result.update(
            code='connection_timeout',
            reason='Connection timed out',
            detail=(
                f'KAORI could not reach {service} at {target}. The connection timed out after '
                f'{timeout_label} while requesting {path}. Check DNS and network access, firewall or proxy '
                f'rules, and confirm that {service} is listening on {scheme}.'
            ),
        )
        return result

    if (
        'NameResolutionError' in names
        or 'name or service not known' in message
        or 'temporary failure in name resolution' in message
        or 'failed to resolve' in message
        or 'nodename nor servname provided' in message
    ):
        result.update(
            code='dns_resolution_failed',
            reason='Hostname could not be resolved',
            detail=(
                f'KAORI could not resolve the {service} hostname {endpoint_context["hostname"]} to an IP address, '
                f'so the request to {path} was not sent. Verify the hostname in the configured endpoint, confirm that '
                'the DNS record exists, and test DNS resolution from the KAORI web and worker containers. If this is '
                'an internal hostname, also confirm that the containers use the required corporate DNS and network or VPN route.'
            ),
        )
        return result

    if (
        'SSLError' in names
        or 'certificate verify failed' in message
        or 'ssl:' in message
        or 'tls' in message
        and 'certificate' in message
    ):
        result.update(
            code='tls_verification_failed',
            reason='TLS certificate verification failed',
            detail=(
                f'KAORI reached {service} at {target}, but TLS certificate verification failed. '
                'Check the certificate hostname, validity period, and issuing CA. Only disable TLS verification '
                'temporarily when the endpoint is trusted and the risk is understood.'
            ),
        )
        return result

    if 'ProxyError' in names or 'proxyerror' in message or 'cannot connect to proxy' in message:
        result.update(
            code='proxy_connection_failed',
            reason='Proxy connection failed',
            detail=(
                f'KAORI could not reach {service} through the configured proxy. Verify proxy settings, '
                f'proxy reachability, and whether {endpoint_context["hostname"]} should be included in NO_PROXY.'
            ),
        )
        return result

    if (
        'connection refused' in message
        or 'newconnectionerror' in message
        or 'failed to establish a new connection' in message
    ):
        result.update(
            code='connection_refused',
            reason='Connection was refused',
            detail=(
                f'KAORI reached {target}, but the connection was refused while requesting {path}. '
                f'Confirm that {service} is running, listening on port {endpoint_context["port"]}, and allowed '
                'by firewall, load balancer, or ingress rules.'
            ),
        )
        return result

    if 'connection reset' in message or 'remotedisconnected' in names or 'remote end closed connection' in message:
        result.update(
            code='connection_reset',
            reason='Connection was closed unexpectedly',
            detail=(
                f'KAORI connected to {target}, but the remote endpoint closed the connection before the '
                f'{service} response was completed. Review reverse-proxy, ingress, TLS, and service logs.'
            ),
        )
        return result

    if (
        {'MetricsSourceAuthenticationError', 'AlertmanagerAuthError'} & names
        or 'authentication failed' in message
        or 'unauthorized' in message
        or 'forbidden' in message
    ):
        result.update(
            code='authentication_failed',
            reason='Authentication was rejected',
            detail=(
                f'{service} at {target} responded, but rejected the configured credentials. '
                'Verify the authentication type, username and password, bearer token, and access permissions.'
            ),
        )
        return result

    status_code = _http_status(chain)
    if status_code is not None:
        if status_code == 404:
            detail = (
                f'{service} at {target} responded with HTTP 404 for {path}. Verify the base endpoint and '
                'make sure the configured URL does not contain an incorrect API path.'
            )
            reason = 'Endpoint path was not found'
            code = 'endpoint_not_found'
        elif status_code == 429:
            detail = (
                f'{service} at {target} responded with HTTP 429. The endpoint is rate limiting requests; '
                'wait briefly and review proxy or service rate-limit settings before retrying.'
            )
            reason = 'Request was rate limited'
            code = 'rate_limited'
        elif 500 <= status_code <= 599:
            detail = (
                f'{service} at {target} responded with HTTP {status_code}. Network connectivity is available, '
                'but the remote service or its proxy reported an internal error. Review service and ingress logs.'
            )
            reason = f'Remote service returned HTTP {status_code}'
            code = 'remote_service_error'
        else:
            detail = (
                f'{service} at {target} responded with HTTP {status_code} for {path}. '
                'Review endpoint configuration, authentication, and reverse-proxy routing.'
            )
            reason = f'Endpoint returned HTTP {status_code}'
            code = 'http_error'

        result.update(
            code=code,
            reason=reason,
            detail=detail,
        )
        return result

    if 'not configured' in message or 'configuration not found' in message:
        result.update(
            code='not_configured',
            reason='Integration is not configured',
            detail=(
                f'{service} is not configured for this cluster. Save a valid endpoint and authentication '
                'configuration before running the connection test.'
            ),
        )

    return result
