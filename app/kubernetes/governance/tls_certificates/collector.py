from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from kubernetes.client import V1Ingress, V1Secret

from app.common.kubernetes_secrets import scrub_secret_payload
from app.integrations.kernel.registry import get_integration
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver import (
    connection_for_cluster,
)
from app.kubernetes.governance.tls_certificates.certificate import (
    TLSValidityPolicy,
    decode_secret_data,
    matching_certificate_pattern,
    parse_certificate,
)
from app.kubernetes.governance.tls_certificates.constants import (
    TLS_COLLECTION_API_UNAVAILABLE,
    TLS_COLLECTION_COLLECTED,
    TLS_COLLECTION_FAILED,
    TLS_COLLECTION_PERMISSION_UNAVAILABLE,
    TLS_COVERAGE_FULL,
    TLS_COVERAGE_NONE,
    TLS_COVERAGE_NOT_REPORTED,
    TLS_COVERAGE_PARTIAL,
    TLS_COVERAGE_UNCOVERED,
    TLS_CRT_KEY,
    TLS_SECRET_TYPE,
    TLS_STATUS_INVALID,
)
from app.kubernetes.governance.tls_certificates.controller_evidence import normalize_tls_controller_owner
from app.models import Cluster

TLSProgressCallback = Callable[[int, str], None]

_TLS_PAGE_SIZE = 100
_TLS_MAX_PAGES = 100
_TLS_REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class TLSCollectionEvidence:
    secret_collection_status: str
    ingress_mapping_status: str
    secret_collection_detail: str | None = None
    ingress_mapping_detail: str | None = None


@dataclass(frozen=True)
class TLSCollectionBatch:
    records: list[dict[str, Any]]
    evidence: TLSCollectionEvidence
    error: str | None = None


def _report_progress(callback: TLSProgressCallback | None, percent: int, message: str) -> None:
    if callback is None:
        return
    callback(max(0, min(int(percent), 100)), message)


def _response_items(response: Any) -> list[Any]:
    if isinstance(response, Mapping):
        raw_items = response.get('items')
    else:
        raw_items = getattr(response, 'items', None)
    if not isinstance(raw_items, list):
        raise ValueError('Kubernetes returned a malformed collection page without an items list.')
    return raw_items


def _next_token(response: Any) -> str:
    metadata = response.get('metadata') if isinstance(response, Mapping) else getattr(response, 'metadata', None)
    if isinstance(metadata, Mapping):
        return str(metadata.get('continue') or metadata.get('_continue') or '')
    return str(getattr(metadata, '_continue', None) or '')


def _collect_pages(
    fetch_page: Callable[[str | None], Any],
    consume_page: Callable[[list[Any]], None],
    *,
    kind: str,
    scrub_secrets: bool = False,
) -> None:
    """A complete paged listing or an error; never commit an incomplete prefix."""
    continuation: str | None = None
    seen: set[str] = set()
    for _ in range(_TLS_MAX_PAGES):
        response = fetch_page(continuation)
        items = _response_items(response)
        try:
            if len(items) > _TLS_PAGE_SIZE:
                raise ValueError(f'Kubernetes returned an oversized {kind} collection page.')
            consume_page(items)
            next_token = _next_token(response)
        finally:
            if scrub_secrets:
                for item in items:
                    scrub_secret_payload(item)
        if not next_token:
            return
        if next_token in seen:
            raise ValueError(f'Kubernetes repeated a {kind} continuation token.')
        seen.add(next_token)
        continuation = next_token
    raise ValueError(f'Kubernetes {kind} collection exceeded the safe page limit.')


def _collection_failure(exc: Exception) -> tuple[str, str]:
    status_code = getattr(exc, 'status', None)
    if status_code == 403:
        return TLS_COLLECTION_PERMISSION_UNAVAILABLE, 'Kubernetes permission is unavailable for this collection source.'
    if status_code == 404:
        return TLS_COLLECTION_API_UNAVAILABLE, 'The required Kubernetes API is unavailable for this cluster.'
    return (
        TLS_COLLECTION_FAILED,
        'Unexpected Kubernetes collection failure. Review inventory worker logs before retrying.',
    )


def build_kubernetes_client(cluster: Cluster):
    return get_integration('container_orchestrator').execute(
        'client.build',
        connection_for_cluster(cluster),
    )


def _secret_key(namespace: str | None, name: str | None) -> tuple[str, str] | None:
    if not namespace or not name:
        return None
    return (namespace, name)


def _has_secret_identity(secret: V1Secret) -> bool:
    metadata = getattr(secret, 'metadata', None)
    return bool(
        metadata
        and str(getattr(metadata, 'namespace', None) or '').strip()
        and str(getattr(metadata, 'name', None) or '').strip()
    )


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
    usage_map: dict[tuple[str, str], dict[str, Any]] = {}

    def consume_page(ingresses: list[Any]) -> None:
        for ingress in ingresses:
            metadata = getattr(ingress, 'metadata', None)
            if not metadata or not getattr(metadata, 'namespace', None) or not getattr(metadata, 'name', None):
                raise ValueError('Kubernetes Ingress collection returned a resource without identity.')
            for usage in _ingress_tls_usage(ingress):
                key = _secret_key(usage.get('namespace'), usage.get('secret_name'))
                if key is None:
                    raise ValueError('Kubernetes Ingress TLS reference is missing its namespace or Secret identity.')
                current = usage_map.setdefault(key, {'used_by': [], 'ingress_hosts': []})
                current['used_by'].append(
                    {
                        'namespace': usage['namespace'],
                        'name': usage['ingress_name'],
                        'hosts': usage['hosts'],
                    }
                )
                current['ingress_hosts'].extend(usage['hosts'])

    networking_api = build_kubernetes_client(cluster).networking_api()
    _collect_pages(
        lambda token: networking_api.list_ingress_for_all_namespaces(
            limit=_TLS_PAGE_SIZE,
            _continue=token,
            _request_timeout=_TLS_REQUEST_TIMEOUT_SECONDS,
        ),
        consume_page,
        kind='Ingress',
    )

    for value in usage_map.values():
        value['ingress_hosts'] = sorted({host for host in value['ingress_hosts'] if host})
        unique_consumers: dict[tuple[str, str], dict[str, Any]] = {}
        for consumer in value['used_by']:
            identity = (
                str(consumer.get('namespace') or ''),
                str(consumer.get('name') or ''),
            )
            current = unique_consumers.setdefault(
                identity,
                {
                    'namespace': identity[0],
                    'name': identity[1],
                    'hosts': [],
                },
            )
            current['hosts'].extend(consumer.get('hosts') or [])
        value['used_by'] = [
            {**consumer, 'hosts': sorted({host for host in consumer['hosts'] if host})}
            for consumer in unique_consumers.values()
        ]

    return usage_map


def _coverage_evidence(
    *,
    ingress_hosts: list[str],
    dns_names: list[str],
    common_name: str | None,
    ingress_mapping_status: str,
) -> tuple[str, int, int, list[str]]:
    declared_hosts = sorted({host for host in ingress_hosts if host})
    if ingress_mapping_status != TLS_COLLECTION_COLLECTED:
        return TLS_COVERAGE_NOT_REPORTED, len(declared_hosts), 0, []
    if not declared_hosts:
        return TLS_COVERAGE_NONE, 0, 0, []

    uncovered = [host for host in declared_hosts if matching_certificate_pattern(host, dns_names, common_name) is None]
    covered_count = len(declared_hosts) - len(uncovered)
    if not uncovered:
        state = TLS_COVERAGE_FULL
    elif covered_count == 0:
        state = TLS_COVERAGE_UNCOVERED
    else:
        state = TLS_COVERAGE_PARTIAL
    return state, len(declared_hosts), covered_count, uncovered


def _qualified_secret_uid(secret: V1Secret) -> str | None:
    """Retain only a canonical immutable Kubernetes object UID.

    Absence/invalid UID downgrades provenance to unknown, while ordinary TLS
    certificate collection remains available. Namespace/name cannot replace
    this identity, and untrusted metadata strings are never displayed.
    """
    raw = getattr(getattr(secret, 'metadata', None), 'uid', None)
    if not isinstance(raw, str) or len(raw) > 64:
        return None
    try:
        parsed = str(UUID(raw))
    except (ValueError, TypeError, AttributeError):
        return None
    return parsed if raw.lower() == parsed else None


def parse_tls_secret(
    secret: V1Secret,
    usage_map: dict[tuple[str, str], dict[str, Any]],
    *,
    ingress_mapping_status: str = TLS_COLLECTION_COLLECTED,
    validity_policy: TLSValidityPolicy | None = None,
) -> dict[str, Any]:
    metadata = secret.metadata
    namespace = metadata.namespace if metadata else ''
    name = metadata.name if metadata else ''
    key = (namespace, name)
    usage = usage_map.get(key, {'used_by': [], 'ingress_hosts': []})
    now = datetime.now(UTC)

    payload: dict[str, Any] = {
        'namespace': namespace,
        'secret_name': name,
        'secret_uid': _qualified_secret_uid(secret),
        'controller_owner_refs': normalize_tls_controller_owner(metadata),
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
        'coverage_state': TLS_COVERAGE_NOT_REPORTED,
        'declared_host_count': len(usage['ingress_hosts']),
        'covered_host_count': 0,
        'uncovered_hosts': [],
        'collected_at': now,
    }

    if secret.type != TLS_SECRET_TYPE:
        payload['parse_error'] = f'Secret type is {secret.type or "unknown"}, not {TLS_SECRET_TYPE}.'
        return payload

    # Data-minimization boundary: only tls.crt is accessed. tls.key and unrelated
    # Secret values are never decoded, logged, persisted, or added to audit metadata.
    cert_data = (secret.data or {}).get(TLS_CRT_KEY)
    if not cert_data:
        payload['parse_error'] = 'Secret is missing tls.crt.'
        return payload

    try:
        parsed = parse_certificate(decode_secret_data(cert_data), policy=validity_policy)
    except Exception as exc:
        payload['parse_error'] = str(exc)
        return payload

    coverage_state, declared_count, covered_count, uncovered_hosts = _coverage_evidence(
        ingress_hosts=usage['ingress_hosts'],
        dns_names=parsed.dns_names,
        common_name=parsed.common_name,
        ingress_mapping_status=ingress_mapping_status,
    )

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
            'coverage_state': coverage_state,
            'declared_host_count': declared_count,
            'covered_host_count': covered_count,
            'uncovered_hosts': uncovered_hosts,
        }
    )

    return payload


def collect_tls_certificate_batch(
    cluster: Cluster,
    *,
    progress_callback: TLSProgressCallback | None = None,
    validity_policy: TLSValidityPolicy | None = None,
) -> TLSCollectionBatch:
    _report_progress(progress_callback, 5, f'Connecting to Kubernetes API for {cluster.name}.')
    _report_progress(progress_callback, 12, f'Collecting Ingress TLS references from {cluster.name}.')
    try:
        usage_map = collect_ingress_tls_usage(cluster)
        ingress_status = TLS_COLLECTION_COLLECTED
        ingress_detail = None
    except Exception as exc:
        usage_map = {}
        ingress_status, ingress_detail = _collection_failure(exc)

    _report_progress(progress_callback, 28, f'Reading Kubernetes Secrets from {cluster.name}.')
    records: list[dict[str, Any]] = []

    def consume_page(items: list[Any]) -> None:
        for secret in items:
            if getattr(secret, 'type', None) != TLS_SECRET_TYPE:
                continue
            if not _has_secret_identity(secret):
                raise ValueError('A Kubernetes TLS Secret is missing required identity metadata.')
            records.append(
                parse_tls_secret(
                    secret,
                    usage_map,
                    ingress_mapping_status=ingress_status,
                    validity_policy=validity_policy,
                )
            )
        # Count only normalized metadata, never hold Secret objects across
        # pages. All API objects are scrubbed before the next provider request.
        index = len(records)
        total_secrets = index
        _report_progress(
            progress_callback,
            min(42 + index, 72),
            f'Parsed {index} of {total_secrets} TLS Secrets from {cluster.name}.',
        )

    try:
        core_api = build_kubernetes_client(cluster).core_api()
        _collect_pages(
            lambda token: core_api.list_secret_for_all_namespaces(
                limit=_TLS_PAGE_SIZE,
                _continue=token,
                _request_timeout=_TLS_REQUEST_TIMEOUT_SECONDS,
            ),
            consume_page,
            kind='Secret',
            scrub_secrets=True,
        )
    except Exception as exc:
        secret_status, secret_detail = _collection_failure(exc)
        return TLSCollectionBatch(
            records=[],
            evidence=TLSCollectionEvidence(
                secret_collection_status=secret_status,
                ingress_mapping_status=ingress_status,
                secret_collection_detail=secret_detail,
                ingress_mapping_detail=ingress_detail,
            ),
            error=secret_detail,
        )

    if not records:
        _report_progress(progress_callback, 72, f'No TLS Secrets require parsing in {cluster.name}.')
    else:
        _report_progress(progress_callback, 72, f'Parsed {len(records)} TLS Secrets from {cluster.name}.')

    return TLSCollectionBatch(
        records=records,
        evidence=TLSCollectionEvidence(
            secret_collection_status=TLS_COLLECTION_COLLECTED,
            ingress_mapping_status=ingress_status,
            secret_collection_detail=None,
            ingress_mapping_detail=ingress_detail,
        ),
    )
