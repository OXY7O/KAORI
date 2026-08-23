from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy import func
from werkzeug.datastructures import MultiDict

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.intelligence.catalog import INTELLIGENCE_CATALOG
from app.intelligence.finding_presentation import (
    build_affected_assets,
    build_affected_items,
    build_evidence_details,
    build_fix_steps,
    compact_recommendation_summary,
    finding_scope_details,
    format_affected_summary,
    recommendation_table_summary,
    recommendation_table_title,
)
from app.intelligence.kubernetes_runtime_recommendations import build_kubernetes_runtime_recommendation_findings
from app.intelligence.object_storage_recommendations import build_object_storage_recommendation_findings
from app.intelligence.recommendation_alerting import (
    decorate_catalog_rules,
    decorate_recommendation_findings,
    matches_alert_handling,
)
from app.intelligence.rule_exceptions import build_rule_exception_view
from app.intelligence.rule_presentation import (
    CATEGORY_OPTIONS,
    DOMAIN_OPTIONS,
    LOGIC_TYPE_OPTIONS,
    PER_PAGE_OPTIONS,
    PROVIDER_OPTIONS,
    SEVERITY_OPTIONS,
    SIGNAL_SOURCE_OPTIONS,
    SOURCE_KIND_OPTIONS,
    STATUS_OPTIONS,
    clean,
    domain_label,
    matches,
    normalize_rule,
    provider_keys,
    provider_label,
    to_int,
)


def _is_active_filter_value(value: str | None) -> bool:
    normalized = clean(value).lower()
    return normalized not in {'', 'all'}


def _count_active_filters(filters: dict[str, str], keys: tuple[str, ...] | None = None) -> int:
    selected_keys = keys or tuple(filters.keys())
    return sum(1 for key in selected_keys if _is_active_filter_value(filters.get(key)))


def _truncate_words(value: str | None, limit: int = 132) -> str:
    text = ' '.join(str(value or '').split())
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(' ', 1)[0].strip()
    return f'{shortened or text[:limit].strip()}…'


def _catalog_table_summary(value: str | None, limit: int = 72) -> str:
    text = ' '.join(str(value or '').split())
    if not text:
        return 'Catalog evidence is available in View Rule.'
    for marker in (' Examples:', ' Example:', ' Examples include:'):
        if marker in text:
            text = text.split(marker, 1)[0].rstrip(' .') + '.'
            break
    first_sentence = text.split('. ', 1)[0].strip()
    if 24 <= len(first_sentence) <= limit:
        return first_sentence.rstrip('.') + '.'
    return compact_recommendation_summary(text, limit=limit)


def _base_payload(args: MultiDict[str, str], *, page_mode: str) -> dict[str, Any]:
    filters = {
        'domain': clean(args.get('domain')),
        'provider': clean(args.get('provider')),
        'category': clean(args.get('category')),
        'severity': clean(args.get('severity')),
        'status': clean(args.get('status')),
        'source_kind': clean(args.get('source_kind')),
        'logic_type': clean(args.get('logic_type')),
        'signal_source': clean(args.get('signal_source')),
        'alert_handling': clean(args.get('alert_handling')),
        'q': clean(args.get('q')),
    }

    per_page = to_int(args.get('per_page'), 5)
    if per_page not in PER_PAGE_OPTIONS:
        per_page = 5

    page = max(to_int(args.get('page'), 1), 1)

    catalog = decorate_catalog_rules([normalize_rule(rule) for rule in INTELLIGENCE_CATALOG])
    source_items = (
        catalog if page_mode == 'catalog' else decorate_recommendation_findings(get_active_recommendation_findings())
    )
    filtered = [
        rule
        for rule in source_items
        if matches(rule, filters) and matches_alert_handling(rule, filters.get('alert_handling'), page_mode=page_mode)
    ]
    total_items = len(filtered)
    total_pages = max(ceil(total_items / per_page), 1)
    page = min(page, total_pages)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    items = filtered[start_index:end_index]

    start_item = start_index + 1 if total_items else 0
    end_item = min(end_index, total_items) if total_items else 0
    item_label = 'catalog rules' if page_mode == 'catalog' else 'recommendations'
    visible_filter_keys = (
        (
            'q',
            'domain',
            'provider',
            'severity',
            'category',
            'source_kind',
            'logic_type',
            'signal_source',
            'status',
        )
        if page_mode == 'catalog'
        else (
            'q',
            'domain',
            'provider',
            'severity',
            'category',
            'source_kind',
            'logic_type',
            'signal_source',
            'alert_handling',
        )
    )
    active_filter_count = _count_active_filters(filters, visible_filter_keys)

    if page_mode == 'catalog':
        for item in items:
            item['table_summary'] = _catalog_table_summary(item.get('catalog_summary') or item.get('summary'), limit=56)
    else:
        for item in items:
            scope_title, scope_supporting = finding_scope_details(item)
            item['scope_title'] = scope_title
            item['scope_supporting'] = scope_supporting
            item['list_title'] = recommendation_table_title(item, limit=96)
            item['list_summary'] = recommendation_table_summary(item, limit=72)

    result_context = {
        'matching_items': total_items,
        'source_items': len(source_items),
        'active_filters': active_filter_count,
        'kubernetes_items': sum(1 for item in filtered if item.get('domain') == 'kubernetes'),
        'object_storage_items': sum(1 for item in filtered if item.get('domain') == 'object_storage'),
        'critical_items': sum(1 for item in filtered if item.get('severity') == 'critical'),
        'warning_items': sum(1 for item in filtered if item.get('severity') == 'warning'),
    }
    if page_mode == 'catalog':
        result_context.update(
            {
                'available_items': sum(1 for rule in filtered if rule.get('status') == 'available'),
                'reserved_items': sum(1 for rule in filtered if rule.get('status') == 'reserved'),
                'imported_items': sum(1 for rule in filtered if rule.get('status') == 'imported_signal'),
            }
        )

    return {
        'page_mode': page_mode,
        'active_filter_count': active_filter_count,
        'filters': filters,
        'filter_options': {
            'domains': DOMAIN_OPTIONS,
            'providers': PROVIDER_OPTIONS,
            'categories': CATEGORY_OPTIONS,
            'severities': SEVERITY_OPTIONS,
            'statuses': STATUS_OPTIONS,
            'source_kinds': SOURCE_KIND_OPTIONS,
            'logic_types': LOGIC_TYPE_OPTIONS,
            'signal_sources': SIGNAL_SOURCE_OPTIONS,
            'alert_handling': [
                {'value': '', 'label': 'All Alert Handling'},
                {'value': 'manual_eligible', 'label': 'Manual Eligible'},
                {'value': 'automatic_eligible', 'label': 'Auto Eligible'},
                {'value': 'escalated', 'label': 'Alert Open'},
                {'value': 'resolved', 'label': 'Resolved Alert'},
                {'value': 'accepted_risk', 'label': 'Accepted Risk'},
                {'value': 'recommendation_only', 'label': 'Recommendation Only'},
            ],
            'per_page': PER_PAGE_OPTIONS,
        },
        'items': items,
        'catalog': catalog,
        'recommendation_findings': source_items if page_mode != 'catalog' else [],
        'result_context': result_context,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total_items,
            'start_item': start_item,
            'end_item': end_item,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': max(page - 1, 1),
            'next_page': min(page + 1, total_pages),
            'label': f'Showing {start_item} - {end_item} of {total_items} {item_label}',
        },
    }


def _build_recommendation_findings(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate currently available catalog rules into actionable findings.

    Catalog remains the rule registry. Recommendations should only show findings
    produced from rules that can be evaluated with the data currently collected.
    Rules that need fields we do not collect yet stay visible in Catalog only.
    """

    rules = {str(rule.get('rule_key')): rule for rule in catalog}
    findings: list[dict[str, Any]] = []

    findings.extend(_build_namespace_quota_findings(rules))
    findings.extend(_build_workload_resource_governance_findings(rules))
    findings.extend(_build_latest_image_findings(rules))
    findings.extend(build_kubernetes_runtime_recommendation_findings(rules))
    findings.extend(_build_storage_binding_findings(rules))
    findings.extend(_build_tls_certificate_findings(rules))
    findings.extend(build_object_storage_recommendation_findings(rules))

    findings = [normalize_rule(finding) for finding in findings]
    for finding in findings:
        finding.setdefault('affected_summary', format_affected_summary(finding))
        finding.setdefault('affected_items', build_affected_items(finding))
        finding.setdefault('affected_assets', build_affected_assets(finding))
        finding.setdefault('evidence_details', build_evidence_details(finding))
        finding.setdefault('fix_steps', build_fix_steps(finding))
    findings.sort(key=lambda item: (_severity_rank(str(item.get('severity'))), str(item.get('title', ''))))
    return findings


def get_active_recommendation_findings(
    *,
    domain: str | None = None,
    asset_key: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return active catalog-backed findings for reusable product surfaces.

    Intelligence owns the multi-domain finding set. Callers scope it explicitly
    by canonical domain and asset key instead of relying on Kubernetes-specific
    filtering arguments.
    """

    catalog = [normalize_rule(rule) for rule in INTELLIGENCE_CATALOG]
    findings = _build_recommendation_findings(catalog)

    selected_domain = clean(domain)
    if selected_domain:
        findings = [finding for finding in findings if clean(str(finding.get('domain'))) == selected_domain]

    selected_asset = clean(asset_key)
    if selected_asset:
        findings = [finding for finding in findings if _finding_asset_key(finding) == selected_asset]

    if limit is not None:
        findings = findings[: max(int(limit), 0)]

    return findings


def _finding_asset_key(finding: dict[str, Any]) -> str:
    evidence = finding.get('evidence')
    if not isinstance(evidence, dict):
        return ''
    return clean(
        str(evidence.get('asset_key') or evidence.get('cluster_id') or evidence.get('object_storage_system_id') or '')
    )


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
    except Exception:
        return {}
    try:
        rows = Cluster.query.filter(Cluster.id.in_(cluster_ids)).all()
    except Exception:
        return {}
    return {str(row.id): str(row.name or row.id) for row in rows}


def _build_namespace_quota_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.namespace.missing_quota')
    if not rule:
        return []
    try:
        from app.models import NamespaceInventory, ResourceQuotaInventory
    except Exception:
        return []
    try:
        namespaces = filter_current_generation(db.session.query(NamespaceInventory), NamespaceInventory).all()
        quota_rows = filter_current_generation(
            db.session.query(ResourceQuotaInventory.cluster_id, ResourceQuotaInventory.namespace),
            ResourceQuotaInventory,
        ).all()
    except Exception:
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


def _build_workload_resource_governance_findings(
    rules: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rule_specs = (
        ('kubernetes.workload.missing_cpu_requests', 'requests', 'cpu', 'CPU request'),
        ('kubernetes.workload.missing_memory_requests', 'requests', 'memory', 'memory request'),
        ('kubernetes.workload.missing_memory_limits', 'limits', 'memory', 'memory limit'),
    )
    enabled = [spec for spec in rule_specs if rules.get(spec[0])]
    if not enabled:
        return []
    try:
        from app.models import WorkloadInventory
    except Exception:
        return []
    try:
        workloads = filter_current_generation(db.session.query(WorkloadInventory), WorkloadInventory).all()
    except Exception:
        return []

    cluster_names = _cluster_name_map({str(row.cluster_id) for row in workloads})
    findings: list[dict[str, Any]] = []
    for row in workloads:
        details = row.details if isinstance(row.details, dict) else {}
        pod_template = details.get('pod_template') if isinstance(details, dict) else None
        if not isinstance(pod_template, dict) or not bool(pod_template.get('reported')):
            continue
        containers = [item for item in list(pod_template.get('containers') or []) if isinstance(item, dict)]
        if not containers or any(not isinstance(item.get('resources'), dict) for item in containers):
            # Older inventory generations do not carry resource declarations. Skip rather than infer missing values.
            continue

        cluster_id = str(row.cluster_id)
        cluster_name = cluster_names.get(cluster_id, cluster_id)
        namespace = str(row.namespace or 'default')
        workload_name = str(row.name or 'workload')
        workload_type = str(row.workload_type or 'Workload')
        for rule_key, resource_group, resource_name, display_name in enabled:
            source_rule = rules.get(rule_key)
            if source_rule is None:
                continue
            missing = []
            for container in containers:
                resources = container.get('resources') if isinstance(container.get('resources'), dict) else {}
                values = resources.get(resource_group) if isinstance(resources, dict) else {}
                values = values if isinstance(values, dict) else {}
                if str(values.get(resource_name) or '').strip():
                    continue
                missing.append(str(container.get('name') or 'container'))
            if not missing:
                continue
            count = len(missing)
            preview = ', '.join(missing[:3])
            if count > 3:
                preview = f'{preview}, +{count - 3} more'
            findings.append(
                _clone_rule_as_finding(
                    source_rule,
                    finding_key=(f'{rule_key}:{cluster_id}:{namespace}:{workload_type.lower()}:{workload_name}'),
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
            )
    return findings


def _build_latest_image_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.workload.latest_image_tag')
    if not rule:
        return []

    try:
        from app.models.inventory import PodInventory
    except Exception:
        return []

    findings: list[dict[str, Any]] = []
    try:
        rows = filter_current_generation(db.session.query(PodInventory), PodInventory).all()
    except Exception:
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
                recommended_action='Pin affected images to immutable tags or digests, then sync inventory again to verify traceability.',
                evidence={'cluster_id': cluster_id, 'namespace': namespace, 'affected_pods': count},
            )
        )

    return findings


def _build_storage_binding_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.storage.binding_state')
    if not rule:
        return []

    try:
        from app.models.inventory import StorageInventory
    except Exception:
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
    except Exception:
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


def _build_tls_certificate_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    expired_rule = rules.get('kubernetes.tls_secret.expired')
    expiring_rule = rules.get('kubernetes.tls_secret.expiring_soon')
    invalid_rule = rules.get('kubernetes.tls_secret.invalid')
    if not expired_rule and not expiring_rule and not invalid_rule:
        return []

    try:
        from app.models import TLSCertificateInventory
    except Exception:
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
    except Exception:
        return []

    cluster_names = _cluster_name_map({str(row.cluster_id) for row in rows})
    findings: list[dict[str, Any]] = []
    for row in rows:
        status_value = str(row.status or 'unknown')
        if status_value == 'expired':
            source_rule = expired_rule
            severity = 'critical'
            priority = 'P1'
            title_status = 'expired'
            recommended_action = (
                'Renew the certificate immediately, update the affected existing Kubernetes TLS Secret, '
                'then validate the Ingress endpoint certificate chain.'
            )
        elif status_value == 'invalid':
            source_rule = invalid_rule
            severity = 'critical'
            priority = 'P1'
            title_status = 'invalid'
            recommended_action = (
                'Replace the invalid TLS Secret data with a valid certificate and matching private key, '
                'then resync TLS inventory.'
            )
        elif status_value == 'critical':
            source_rule = expiring_rule
            severity = 'critical'
            priority = 'P1'
            title_status = 'critically close to expiry'
            recommended_action = (
                'Prioritize renewal during the next safe maintenance window and use TLS Secret Update '
                'to validate and apply the replacement certificate.'
            )
        else:
            source_rule = expiring_rule
            severity = 'warning'
            priority = 'P2'
            title_status = 'approaching expiry'
            recommended_action = (
                'Prepare the renewed certificate pair and schedule update before the certificate enters '
                'the critical expiry window.'
            )

        if not source_rule:
            continue

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


def _severity_rank(value: str) -> int:
    return {
        'critical': 0,
        'warning': 1,
        'info': 2,
        'success': 3,
    }.get(value.lower(), 9)


def get_catalog_rule(rule_key: str) -> dict[str, Any] | None:
    """Return one normalized catalog definition by its canonical rule key."""

    resolved_key = clean(rule_key)
    if not resolved_key:
        return None

    for raw_rule in INTELLIGENCE_CATALOG:
        rule = normalize_rule(dict(raw_rule))
        if clean(str(rule.get('rule_key'))) == resolved_key:
            decorate_catalog_rules([rule])
            exception_policy = rule.get('risk_exception') if isinstance(rule.get('risk_exception'), dict) else {}
            if bool(exception_policy.get('enabled')):
                exception_view = build_rule_exception_view(
                    resolved_key,
                    get_active_recommendation_findings(),
                )
                exception_view['policy'] = dict(exception_policy)
                rule['rule_exceptions'] = exception_view
            else:
                rule['rule_exceptions'] = None
            return rule
    return None


def get_recommendation_finding(recommendation_key: str) -> dict[str, Any] | None:
    """Return one active recommendation finding by its canonical finding key."""

    resolved_key = clean(recommendation_key)
    if not resolved_key:
        return None

    for finding in get_active_recommendation_findings():
        if clean(str(finding.get('rule_key'))) != resolved_key:
            continue

        scope_title, scope_supporting = finding_scope_details(finding)
        finding['scope_title'] = scope_title
        finding['scope_supporting'] = scope_supporting
        finding['list_title'] = recommendation_table_title(finding, limit=96)
        finding['list_summary'] = recommendation_table_summary(finding, limit=72)
        decorate_recommendation_findings([finding])
        return finding

    return None


def _catalog_scope_label(filters: dict[str, str]) -> str:
    selected_domain = clean(filters.get('domain'))
    selected_provider = clean(filters.get('provider'))
    scope_parts: list[str] = []
    if selected_domain:
        scope_parts.append(domain_label(selected_domain))
    if selected_provider:
        scope_parts.append(provider_label([selected_provider]))
    return ' · '.join(scope_parts) if scope_parts else 'Multi-Domain'


def _apply_catalog_payload(
    payload: dict[str, Any],
    catalog: list[dict[str, Any]],
    *,
    available: int,
    reserved: int,
    imported: int,
) -> None:
    catalog_domains = {str(rule.get('domain') or '') for rule in catalog if rule.get('domain')}
    minio_coverage = sum(1 for rule in catalog if 'minio' in provider_keys(rule))
    object_storage_rules = sum(1 for rule in catalog if rule.get('domain') == 'object_storage')
    payload.update(
        {
            'page_title': 'Rule Catalog',
            'scope_label': _catalog_scope_label(payload['filters']),
            'summary': {
                'available': available,
                'reserved': reserved,
                'imported': imported,
                'domains': len(catalog_domains),
                'object_storage': object_storage_rules,
                'minio': minio_coverage,
            },
            'posture': {
                'title': 'Catalog Posture',
                'label': 'Active Coverage' if available else 'Reserved Plan',
                'tone': 'normal' if available else 'unknown',
            },
        }
    )


def _apply_recommendation_payload(payload: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    critical = sum(1 for item in findings if item.get('severity') == 'critical')
    warning = sum(1 for item in findings if item.get('severity') == 'warning')
    selected_domain = clean(payload['filters'].get('domain'))
    scope_label = domain_label(selected_domain) if selected_domain else 'Multi-Domain'
    posture_tone = 'critical' if critical else ('warning' if warning else 'normal')
    if critical:
        posture_label = 'Critical'
    elif warning:
        posture_label = 'Review'
    elif findings:
        posture_label = 'Active'
    else:
        posture_label = 'No Active Findings'
    active_domains = {str(item.get('domain') or '') for item in findings if item.get('domain')}
    payload.update(
        {
            'page_title': 'Recommendations',
            'scope_label': scope_label,
            'summary': {
                'actionable': len(findings),
                'critical': critical,
                'warning': warning,
                'domains': len(active_domains),
                'object_storage': sum(1 for item in findings if item.get('domain') == 'object_storage'),
                'alert_eligible': sum(1 for item in findings if (item.get('alert_handling') or {}).get('eligible')),
                'alert_open': sum(
                    1 for item in findings if (item.get('alert_handling') or {}).get('status') == 'escalated'
                ),
            },
            'posture': {
                'title': 'Recommendation Posture',
                'label': posture_label,
                'tone': posture_tone,
            },
        }
    )


def get_recommendations_payload(args: MultiDict[str, str], *, page_mode: str = 'recommendations') -> dict[str, Any]:
    payload = _base_payload(args, page_mode=page_mode)
    catalog = payload['catalog']
    findings = payload['recommendation_findings'] if page_mode != 'catalog' else []

    if page_mode == 'catalog':
        _apply_catalog_payload(
            payload,
            catalog,
            available=sum(1 for rule in catalog if rule.get('status') == 'available'),
            reserved=sum(1 for rule in catalog if rule.get('status') == 'reserved'),
            imported=sum(1 for rule in catalog if rule.get('status') == 'imported_signal'),
        )
    else:
        _apply_recommendation_payload(payload, findings)
    return payload
