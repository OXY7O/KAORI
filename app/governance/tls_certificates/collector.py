from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import V1Ingress, V1Secret

from app.governance.tls_certificates.certificate import decode_secret_data, parse_certificate
from app.governance.tls_certificates.constants import TLS_CRT_KEY, TLS_SECRET_TYPE, TLS_STATUS_INVALID
from app.integrations.kubernetes.tls import weak_tls_context
from app.integrations.registry import get_integration
from app.models import Cluster


def _response_items(response: Any) -> list[Any]:
    if isinstance(response, Mapping):
        raw_items = response.get('items')
    else:
        raw_items = getattr(response, 'items', None)
    if not isinstance(raw_items, list):
        return []
    return raw_items


def build_kubernetes_client(cluster: Cluster):
    return get_integration('kubernetes').execute(
        'client.build',
        cluster.kubernetes_connection,
    )


def _secret_key(namespace: str | None, name: str | None) -> tuple[str, str] | None:
    if not namespace or not name:
        return None
    return (namespace, name)


def _ingress_tls_usage(ingress: V1Ingress) -> list[dict[str, Any]]:
    metadata = ingress.metadata
    spec = ingress.spec

    if not metadata or not spec or not spec.tls:
        return []

    usage: list[dict[str, Any]] = []
    for tls_entry in spec.tls:
        secret_name = getattr(tls_entry, 'secret_name', None)
        if not secret_name:
            continue

        usage.append(
            {
                'namespace': metadata.namespace,
                'ingress_name': metadata.name,
                'secret_name': secret_name,
                'hosts': list(getattr(tls_entry, 'hosts', None) or []),
            }
        )

    return usage


def collect_ingress_tls_usage(cluster: Cluster) -> dict[tuple[str, str], dict[str, Any]]:
    with weak_tls_context(enabled=bool(cluster.kubernetes_connection.allow_weak_tls)):
        client = build_kubernetes_client(cluster)
        networking_api = client.networking_api()
        response = networking_api.list_ingress_for_all_namespaces()

    usage_map: dict[tuple[str, str], dict[str, Any]] = {}
    for ingress in _response_items(response):
        for usage in _ingress_tls_usage(ingress):
            key = _secret_key(usage.get('namespace'), usage.get('secret_name'))
            if key is None:
                continue

            current = usage_map.setdefault(key, {'used_by': [], 'ingress_hosts': []})
            current['used_by'].append(
                {
                    'namespace': usage['namespace'],
                    'name': usage['ingress_name'],
                    'hosts': usage['hosts'],
                }
            )
            current['ingress_hosts'].extend(usage['hosts'])

    for value in usage_map.values():
        value['ingress_hosts'] = sorted({host for host in value['ingress_hosts'] if host})

    return usage_map


def parse_tls_secret(secret: V1Secret, usage_map: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    metadata = secret.metadata
    namespace = metadata.namespace if metadata else ''
    name = metadata.name if metadata else ''
    key = (namespace, name)
    usage = usage_map.get(key, {'used_by': [], 'ingress_hosts': []})
    data = secret.data or {}
    now = datetime.now(UTC)

    payload: dict[str, Any] = {
        'namespace': namespace,
        'secret_name': name,
        'secret_type': secret.type,
        'common_name': None,
        'issuer': None,
        'serial_number': None,
        'fingerprint_sha256': None,
        'dns_names': [],
        'ingress_hosts': usage['ingress_hosts'],
        'used_by': usage['used_by'],
        'not_before': None,
        'not_after': None,
        'days_remaining': None,
        'status': TLS_STATUS_INVALID,
        'risk_level': 'critical',
        'parse_error': None,
        'collected_at': now,
    }

    if secret.type != TLS_SECRET_TYPE:
        payload['parse_error'] = f'Secret type is {secret.type or "unknown"}, not {TLS_SECRET_TYPE}.'
        return payload

    cert_data = data.get(TLS_CRT_KEY)
    if not cert_data:
        payload['parse_error'] = 'Secret is missing tls.crt.'
        return payload

    try:
        parsed = parse_certificate(decode_secret_data(cert_data))
    except Exception as exc:
        payload['parse_error'] = str(exc)
        return payload

    payload.update(
        {
            'common_name': parsed.common_name,
            'issuer': parsed.issuer,
            'serial_number': parsed.serial_number,
            'fingerprint_sha256': parsed.fingerprint_sha256,
            'dns_names': parsed.dns_names,
            'not_before': parsed.not_before,
            'not_after': parsed.not_after,
            'days_remaining': parsed.days_remaining,
            'status': parsed.status,
            'risk_level': parsed.risk_level,
            'parse_error': None,
        }
    )

    return payload


def collect_tls_certificates(cluster: Cluster) -> list[dict[str, Any]]:
    try:
        usage_map = collect_ingress_tls_usage(cluster)
    except Exception:
        usage_map = {}

    with weak_tls_context(enabled=bool(cluster.kubernetes_connection.allow_weak_tls)):
        client = build_kubernetes_client(cluster)
        core_api = client.core_api()
        response = core_api.list_secret_for_all_namespaces()

    records: list[dict[str, Any]] = []
    for secret in _response_items(response):
        if secret.type == TLS_SECRET_TYPE:
            records.append(parse_tls_secret(secret, usage_map))

    return records
