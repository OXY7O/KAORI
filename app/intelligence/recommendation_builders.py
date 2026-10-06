from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.intelligence.finding_presentation import (
    build_affected_assets,
    build_affected_items,
    build_evidence_details,
    build_fix_steps,
    format_affected_summary,
)
from app.intelligence.rule_presentation import normalize_rule


def _clone_rule_as_finding(
    rule: dict[str, Any],
    *,
    finding_key: str,
    title: str,
    summary: str,
    condition_summary: str,
    recommended_action: str | None = None,
    impact: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = dict(rule)
    output['rule_key'] = finding_key
    output['title'] = title
    output['summary'] = summary
    output['condition_summary'] = condition_summary
    output['recommended_action'] = recommended_action or str(rule.get('recommended_action') or '')
    output['impact'] = impact or str(rule.get('impact') or '')
    output['status'] = 'available'
    output['evidence'] = evidence or {}
    output.setdefault('affected_summary', format_affected_summary(output))
    output.setdefault('affected_items', build_affected_items(output))
    output.setdefault('affected_assets', build_affected_assets(output))
    output.setdefault('evidence_details', build_evidence_details(output))
    output.setdefault('fix_steps', build_fix_steps(output))
    return output


def _cluster_name_map(cluster_ids: set[str]) -> dict[str, str]:
    if not cluster_ids:
        return {}
    try:
        from app.models import Cluster
    except ImportError:
        return {}
    try:
        rows = Cluster.query.filter(Cluster.id.in_(cluster_ids)).all()
    except SQLAlchemyError:
        return {}
    return {str(row.id): str(row.name or row.id) for row in rows}


def build_namespace_quota_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.namespace.missing_quota')
    if not rule:
        return []
    try:
        from app.models import NamespaceInventory, ResourceQuotaInventory
    except ImportError:
        return []
    try:
        namespaces = filter_current_generation(db.session.query(NamespaceInventory), NamespaceInventory).all()
        quota_rows = filter_current_generation(
            db.session.query(ResourceQuotaInventory.cluster_id, ResourceQuotaInventory.namespace),
            ResourceQuotaInventory,
        ).all()
    except SQLAlchemyError:
        return []

    quota_namespaces = {(str(cluster_id), str(namespace)) for cluster_id, namespace in quota_rows}
    cluster_names = _cluster_name_map({str(row.cluster_id) for row in namespaces})
    findings: list[dict[str, Any]] = []
    for row in namespaces:
        cluster_id = str(row.cluster_id)
        namespace = str(row.namespace or 'default')
        if (cluster_id, namespace) in quota_namespaces:
            continue
        cluster_name = cluster_names.get(cluster_id, cluster_id)
        findings.append(
            _clone_rule_as_finding(
                rule,
                finding_key=f'kubernetes.namespace.missing_quota:{cluster_id}:{namespace}',
                title=f'Namespace {namespace} has no ResourceQuota',
                summary=(
                    f'Namespace {namespace} in {cluster_name} has no ResourceQuota in the latest committed '
                    'Kubernetes inventory.'
                ),
                condition_summary=(
                    'No ResourceQuota object is present for this namespace in the current inventory generation.'
                ),
                evidence={
                    'cluster_id': cluster_id,
                    'cluster_name': cluster_name,
                    'namespace': namespace,
                    'affected_count': 1,
                    'quota_count': 0,
                },
            )
        )
    return findings


def _missing_resource_containers(
    containers: list[dict[str, Any]],
    *,
    resource_group: str,
    resource_name: str,
) -> list[str]:
    missing: list[str] = []
    for container in containers:
        resources = container.get('resources')
        resource_map = resources if isinstance(resources, dict) else {}
        values = resource_map.get(resource_group)
        group_values = values if isinstance(values, dict) else {}
        if str(group_values.get(resource_name) or '').strip():
            continue
        missing.append(str(container.get('name') or 'container'))
    return missing


def _resource_governance_finding(
    source_rule: dict[str, Any],
    *,
    rule_key: str,
    resource_group: str,
    resource_name: str,
    display_name: str,
    row: Any,
    cluster_name: str,
    containers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    missing = _missing_resource_containers(
        containers,
        resource_group=resource_group,
        resource_name=resource_name,
    )
    if not missing:
        return None
    cluster_id = str(row.cluster_id)
    namespace = str(row.namespace or 'default')
    workload_name = str(row.name or 'workload')
    workload_type = str(row.workload_type or 'Workload')
    count = len(missing)
    preview = ', '.join(missing[:3])
    if count > 3:
        preview = f'{preview}, +{count - 3} more'
    return _clone_rule_as_finding(
        source_rule,
        finding_key=f'{rule_key}:{cluster_id}:{namespace}:{workload_type.lower()}:{workload_name}',
        title=f'{workload_type} {workload_name} is missing {display_name}',
        summary=(
            f'{workload_type} {workload_name} in namespace {namespace} has {count} container'
            f'{"s" if count != 1 else ""} without {display_name}. Affected: {preview}.'
        ),
        condition_summary=(
            f'One or more workload containers do not define resources.{resource_group}.{resource_name} '
            'in the latest committed workload inventory.'
        ),
        evidence={
            'cluster_id': cluster_id,
            'cluster_name': cluster_name,
            'namespace': namespace,
            'workload_name': workload_name,
            'workload_type': workload_type,
            'affected_count': count,
            'missing_containers': missing[:10],
            'resource_field': f'resources.{resource_group}.{resource_name}',
        },
    )


def build_workload_resource_governance_findings(
    rules: dict[str, dict[str, Any]],
    *,
    rule_specs: tuple[tuple[str, str, str, str], ...],
) -> list[dict[str, Any]]:
    enabled = [spec for spec in rule_specs if rules.get(spec[0])]
    if not enabled:
        return []
    try:
        from app.models import WorkloadInventory
    except ImportError:
        return []
    try:
        workloads = filter_current_generation(db.session.query(WorkloadInventory), WorkloadInventory).all()
    except SQLAlchemyError:
        return []

    cluster_names = _cluster_name_map({str(row.cluster_id) for row in workloads})
    findings: list[dict[str, Any]] = []
    for row in workloads:
        details = row.details if isinstance(row.details, dict) else {}
        pod_template = details.get('pod_template')
        if not isinstance(pod_template, dict) or not bool(pod_template.get('reported')):
            continue
        containers = [item for item in list(pod_template.get('containers') or []) if isinstance(item, dict)]
        if not containers or any(not isinstance(item.get('resources'), dict) for item in containers):
            continue
        cluster_id = str(row.cluster_id)
        cluster_name = cluster_names.get(cluster_id, cluster_id)
        for rule_key, resource_group, resource_name, display_name in enabled:
            source_rule = rules.get(rule_key)
            if source_rule is None:
                continue
            finding = _resource_governance_finding(
                source_rule,
                rule_key=rule_key,
                resource_group=resource_group,
                resource_name=resource_name,
                display_name=display_name,
                row=row,
                cluster_name=cluster_name,
                containers=containers,
            )
            if finding is not None:
                findings.append(finding)
    return findings


def build_latest_image_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.workload.latest_image_tag')
    if not rule:
        return []
    try:
        from app.models.inventory import PodInventory
    except ImportError:
        return []
    try:
        rows = filter_current_generation(db.session.query(PodInventory), PodInventory).all()
    except SQLAlchemyError:
        return []

    affected: dict[tuple[str, str], set[str]] = {}
    examples: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        images = list(getattr(row, 'container_images', None) or []) + list(
            getattr(row, 'init_container_images', None) or []
        )
        mutable_images = [image for image in images if _is_mutable_image_reference(str(image))]
        if not mutable_images:
            continue
        key = (str(getattr(row, 'cluster_id', '')), str(getattr(row, 'namespace', 'default') or 'default'))
        affected.setdefault(key, set()).add(str(getattr(row, 'pod_name', 'pod')))
        examples.setdefault(key, [])
        for image in mutable_images:
            if image not in examples[key] and len(examples[key]) < 3:
                examples[key].append(image)

    findings: list[dict[str, Any]] = []
    for (cluster_id, namespace), pods in affected.items():
        count = len(pods)
        example_text = ', '.join(examples.get((cluster_id, namespace), [])) or 'mutable image reference'
        findings.append(
            _clone_rule_as_finding(
                rule,
                finding_key=f'{rule["rule_key"]}:{cluster_id}:{namespace}',
                title=f'{count} pod{"s" if count != 1 else ""} use mutable image references in {namespace}',
                summary=(
                    f'{count} pod{"s" if count != 1 else ""} in namespace {namespace} use :latest or unpinned image references. '
                    f'Examples: {example_text}.'
                ),
                condition_summary='A collected pod image ends with :latest or has no immutable tag/digest.',
                recommended_action=(
                    'Pin affected images to immutable tags or digests, then sync inventory again to verify traceability.'
                ),
                evidence={'cluster_id': cluster_id, 'namespace': namespace, 'affected_pods': count},
            )
        )
    return findings


def build_storage_binding_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.storage.binding_state')
    if not rule:
        return []
    try:
        from app.models.inventory import StorageInventory
    except ImportError:
        return []
    try:
        query = db.session.query(
            StorageInventory.cluster_id,
            StorageInventory.namespace,
            StorageInventory.status,
            func.count(StorageInventory.id),
        ).filter(StorageInventory.status.notin_(['Bound', 'Available']))
        rows = (
            filter_current_generation(query, StorageInventory)
            .group_by(StorageInventory.cluster_id, StorageInventory.namespace, StorageInventory.status)
            .all()
        )
    except SQLAlchemyError:
        return []

    findings: list[dict[str, Any]] = []
    for cluster_id, namespace, status, count in rows:
        namespace_label = str(namespace or 'cluster scope')
        status_label = str(status or 'Unknown')
        findings.append(
            _clone_rule_as_finding(
                rule,
                finding_key=f'kubernetes.storage.binding_state:{cluster_id}:{namespace}:{status}',
                title=f'{count} storage object{"s" if int(count) != 1 else ""} need review in {namespace_label}',
                summary=f'Storage inventory shows {count} object{"s" if int(count) != 1 else ""} with status {status_label}.',
                condition_summary='Collected storage object status is not Bound or Available.',
                evidence={
                    'cluster_id': str(cluster_id),
                    'namespace': namespace_label,
                    'affected_count': int(count),
                    'status': status_label,
                },
            )
        )
    return findings


def _tls_finding_profile(status_value: str) -> tuple[str, str, str, str]:
    if status_value == 'expired':
        return (
            'critical',
            'P1',
            'expired',
            'Renew the certificate immediately, update the affected existing Kubernetes TLS Secret, then validate the Ingress endpoint certificate chain.',
        )
    if status_value == 'invalid':
        return (
            'critical',
            'P1',
            'invalid',
            'Replace the invalid TLS Secret data with a valid certificate and matching private key, then resync TLS inventory.',
        )
    if status_value == 'critical':
        return (
            'critical',
            'P1',
            'critically close to expiry',
            'Prioritize renewal during the next safe maintenance window and use TLS Secret Update to validate and apply the replacement certificate.',
        )
    return (
        'warning',
        'P2',
        'approaching expiry',
        'Prepare the renewed certificate pair and schedule update before the certificate enters the critical expiry window.',
    )


def build_tls_certificate_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    expired_rule = rules.get('kubernetes.tls_secret.expired')
    expiring_rule = rules.get('kubernetes.tls_secret.expiring_soon')
    invalid_rule = rules.get('kubernetes.tls_secret.invalid')
    if not expired_rule and not expiring_rule and not invalid_rule:
        return []
    try:
        from app.models import TLSCertificateInventory
    except ImportError:
        return []
    try:
        rows = (
            TLSCertificateInventory.query.filter(
                TLSCertificateInventory.status.in_(['expired', 'critical', 'warning', 'invalid'])
            )
            .order_by(
                TLSCertificateInventory.cluster_id.asc(),
                TLSCertificateInventory.namespace.asc(),
                TLSCertificateInventory.days_remaining.asc().nullslast(),
                TLSCertificateInventory.secret_name.asc(),
            )
            .all()
        )
    except SQLAlchemyError:
        return []

    cluster_names = _cluster_name_map({str(row.cluster_id) for row in rows})
    findings: list[dict[str, Any]] = []
    for row in rows:
        status_value = str(row.status or 'unknown')
        source_rule = (
            invalid_rule if status_value == 'invalid' else expired_rule if status_value == 'expired' else expiring_rule
        )
        if not source_rule:
            continue
        severity, priority, title_status, recommended_action = _tls_finding_profile(status_value)
        cluster_id = str(row.cluster_id)
        cluster_name = cluster_names.get(cluster_id, cluster_id)
        namespace = str(row.namespace or 'default')
        secret_name = str(row.secret_name or 'tls-secret')
        days_remaining = row.days_remaining
        affected_hosts = list(row.ingress_hosts or [])[:5]
        source_rule_key = str(source_rule.get('rule_key') or '')
        findings.append(
            normalize_rule(
                {
                    **source_rule,
                    'rule_key': f'{source_rule_key}:{cluster_id}:{namespace}:{secret_name}',
                    'title': f'TLS Secret {secret_name} is {title_status}',
                    'severity': severity,
                    'priority': priority,
                    'status': 'available',
                    'summary': (
                        f'TLS Secret {secret_name} in namespace {namespace} reports {status_value} certificate '
                        f'posture with {days_remaining if days_remaining is not None else "unknown"} day(s) remaining.'
                    ),
                    'condition_summary': (
                        f'Collected TLS Secret {secret_name} status is {status_value}; remaining certificate '
                        f'lifetime is {days_remaining if days_remaining is not None else "unknown"} day(s).'
                    ),
                    'recommended_action': recommended_action,
                    'impact': str(
                        source_rule.get('impact') or 'Protects HTTPS availability and certificate governance readiness.'
                    ),
                    'visible_in': ['Recommendations', 'Kubernetes TLS Secret', 'TLS Secret Update', 'Reports'],
                    'evidence': {
                        'cluster_id': cluster_id,
                        'cluster_name': cluster_name,
                        'namespace': namespace,
                        'secret_name': secret_name,
                        'affected_count': 1,
                        'status': status_value,
                        'issuer': str(row.issuer or ''),
                        'days_remaining': days_remaining,
                        'affected_hosts': ', '.join(affected_hosts),
                        'fingerprint_sha256': str(row.fingerprint_sha256 or ''),
                    },
                }
            )
        )
    return findings


def _is_mutable_image_reference(image: str) -> bool:
    if not image or '@sha256:' in image:
        return False
    image_without_registry_port = image.rsplit('/', 1)[-1]
    return ':' not in image_without_registry_port or image.endswith(':latest')
