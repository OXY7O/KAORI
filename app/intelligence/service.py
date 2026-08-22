from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy import func
from werkzeug.datastructures import MultiDict

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.intelligence.catalog import INTELLIGENCE_CATALOG, minimum_severity_band_value, severity_for_observed_value
from app.intelligence.finding_evidence import build_restart_evidence, build_restart_groups
from app.intelligence.finding_presentation import (
    build_affected_assets,
    build_affected_items,
    build_evidence_details,
    build_fix_steps,
    finding_scope_details,
    format_affected_summary,
    recommendation_table_summary,
    recommendation_table_title,
)
from app.intelligence.object_storage_recommendations import build_object_storage_recommendation_findings
from app.intelligence.recommendation_alerting import (
    decorate_catalog_rules,
    decorate_recommendation_findings,
    matches_alert_handling,
)
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
            item['table_summary'] = _truncate_words(item.get('summary'), limit=64)
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

    findings.extend(_build_latest_image_findings(rules))
    findings.extend(_build_pod_health_findings(rules))
    findings.extend(_build_node_readiness_findings(rules))
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


def _build_pod_health_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    unhealthy_rule = rules.get('kubernetes.pod.unhealthy_phase')
    restart_rule = rules.get('kubernetes.pod.high_restart_count')
    if not unhealthy_rule and not restart_rule:
        return []

    try:
        from app.models.inventory import PodInventory
    except Exception:
        return []

    restart_threshold = minimum_severity_band_value(restart_rule, default=5) if restart_rule else 5
    try:
        unhealthy_query = db.session.query(
            PodInventory.cluster_id,
            PodInventory.namespace,
            PodInventory.phase,
            func.count(PodInventory.id),
        ).filter(PodInventory.phase.notin_(['Running', 'Succeeded']))
        unhealthy_rows = (
            filter_current_generation(unhealthy_query, PodInventory)
            .group_by(PodInventory.cluster_id, PodInventory.namespace, PodInventory.phase)
            .all()
        )
        restart_query = db.session.query(
            PodInventory.cluster_id,
            PodInventory.namespace,
            PodInventory.pod_name,
            PodInventory.restart_count,
            PodInventory.phase,
            PodInventory.node_name,
            PodInventory.workload_type,
            PodInventory.workload_name,
        ).filter(PodInventory.restart_count >= restart_threshold)
        restart_rows = filter_current_generation(restart_query, PodInventory).all()
    except Exception:
        return []

    findings: list[dict[str, Any]] = []
    if unhealthy_rule:
        for cluster_id, namespace, phase, count in unhealthy_rows:
            findings.append(
                _clone_rule_as_finding(
                    unhealthy_rule,
                    finding_key=f'kubernetes.pod.unhealthy_phase:{cluster_id}:{namespace}:{phase}',
                    title=f'{count} pod{"s" if int(count) != 1 else ""} in {namespace} are {phase or "not healthy"}',
                    summary=(
                        f'Pod inventory shows {count} pod{"s" if int(count) != 1 else ""} '
                        f'in phase {phase or "Unknown"}.'
                    ),
                    condition_summary='Collected pod phase is not Running or Succeeded.',
                    evidence={
                        'cluster_id': str(cluster_id),
                        'namespace': str(namespace),
                        'affected_count': int(count),
                        'phase': str(phase or 'Unknown'),
                        'observed_total_display': f'{count} affected pod{"" if int(count) == 1 else "s"}',
                        'snapshot_basis': 'Current Pod Inventory generation',
                    },
                )
            )

    if restart_rule:
        for (cluster_id, namespace), assets in build_restart_groups(restart_rows).items():
            evidence = build_restart_evidence(
                cluster_id=cluster_id,
                namespace=namespace,
                assets=assets,
                threshold=restart_threshold,
            )
            affected_count = int(evidence['affected_count'])
            max_restarts = int(evidence['max_restart_count'])
            max_pod = str(evidence['max_restart_pod'])
            finding_severity = severity_for_observed_value(restart_rule, max_restarts)
            findings.append(
                _clone_rule_as_finding(
                    {**restart_rule, 'severity': finding_severity},
                    finding_key=f'kubernetes.pod.high_restart_count:{cluster_id}:{namespace}',
                    title=(
                        f'Pod {max_pod} reports {max_restarts} restarts'
                        if affected_count == 1
                        else f'{affected_count} pods in {namespace} have repeated restarts (max {max_restarts})'
                    ),
                    summary=(
                        f'Latest committed Pod Inventory shows {affected_count} affected pod'
                        f'{"" if affected_count == 1 else "s"}; {max_pod} has the highest observed restart count at '
                        f'{max_restarts}, with {evidence["total_restart_count"]} total restarts '
                        'across the affected set.'
                    ),
                    condition_summary=(
                        f'Each affected pod has restart_count greater than or equal to {restart_threshold} '
                        'in the latest committed Pod Inventory generation.'
                    ),
                    evidence=evidence,
                )
            )

    return findings


def _build_node_readiness_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.node.not_ready')
    if not rule:
        return []

    try:
        from app.models.inventory import NodeInventory
    except Exception:
        return []

    try:
        query = db.session.query(NodeInventory.cluster_id, func.count(NodeInventory.id)).filter(
            NodeInventory.status != 'Ready'
        )
        rows = filter_current_generation(query, NodeInventory).group_by(NodeInventory.cluster_id).all()
    except Exception:
        return []

    return [
        _clone_rule_as_finding(
            rule,
            finding_key=f'kubernetes.node.not_ready:{cluster_id}',
            title=f'{count} node{"s" if int(count) != 1 else ""} are not Ready',
            summary=f'Node inventory shows {count} node{"s" if int(count) != 1 else ""} outside Ready state.',
            condition_summary='Collected node status is not Ready.',
            evidence={'cluster_id': str(cluster_id), 'affected_count': int(count)},
        )
        for cluster_id, count in rows
    ]


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
            db.session.query(
                TLSCertificateInventory.cluster_id,
                TLSCertificateInventory.namespace,
                TLSCertificateInventory.status,
                func.count(TLSCertificateInventory.id),
                func.min(TLSCertificateInventory.days_remaining),
            )
            .filter(TLSCertificateInventory.status.in_(['expired', 'critical', 'warning', 'invalid']))
            .group_by(
                TLSCertificateInventory.cluster_id,
                TLSCertificateInventory.namespace,
                TLSCertificateInventory.status,
            )
            .all()
        )
    except Exception:
        return []

    findings: list[dict[str, Any]] = []
    for cluster_id, namespace, status, count, min_days_remaining in rows:
        status_value = str(status or 'unknown')
        if status_value == 'expired':
            source_rule = expired_rule
            severity = 'critical'
            priority = 'P1'
            title_status = 'expired'
            recommended_action = 'Renew the certificate immediately, update the affected existing Kubernetes TLS Secret, then validate the Ingress endpoint certificate chain.'
        elif status_value == 'invalid':
            source_rule = invalid_rule
            severity = 'critical'
            priority = 'P1'
            title_status = 'invalid'
            recommended_action = 'Replace the invalid TLS Secret data with a valid certificate and matching private key, then resync TLS inventory.'
        elif status_value == 'critical':
            source_rule = expiring_rule
            severity = 'critical'
            priority = 'P1'
            title_status = 'critically close to expiry'
            recommended_action = 'Prioritize renewal during the next safe maintenance window and use TLS Secret Update to validate and apply the replacement certificate.'
        else:
            source_rule = expiring_rule
            severity = 'warning'
            priority = 'P2'
            title_status = 'approaching expiry'
            recommended_action = 'Prepare the renewed certificate pair and schedule update before the certificate enters the critical expiry window.'

        if not source_rule:
            continue

        try:
            example = (
                TLSCertificateInventory.query.filter(
                    TLSCertificateInventory.cluster_id == cluster_id,
                    TLSCertificateInventory.namespace == namespace,
                    TLSCertificateInventory.status == status_value,
                )
                .order_by(TLSCertificateInventory.days_remaining.asc().nullslast())
                .first()
            )
        except Exception:
            example = None

        secret_label = 'TLS Secret' if int(count) == 1 else 'TLS Secrets'
        namespace_label = namespace or 'cluster scope'
        example_secret = str(getattr(example, 'secret_name', '') or '')
        issuer = str(getattr(example, 'issuer', '') or '')
        days_remaining = getattr(example, 'days_remaining', None)
        affected_hosts = list(getattr(example, 'ingress_hosts', None) or [])[:3] if example else []

        findings.append(
            normalize_rule(
                {
                    **source_rule,
                    'rule_key': f'kubernetes.tls_secret.{status_value}:{cluster_id}:{namespace}',
                    'title': f'{count} {secret_label} {title_status} in {namespace_label}',
                    'severity': severity,
                    'priority': priority,
                    'status': 'available',
                    'summary': f'TLS Secret inventory shows {count} {secret_label.lower()} with {status_value} certificate posture in namespace {namespace_label}.',
                    'condition_summary': f'Collected TLS Secret status is {status_value}; minimum remaining lifetime is {min_days_remaining if min_days_remaining is not None else "unknown"} day(s).',
                    'recommended_action': recommended_action,
                    'impact': str(
                        source_rule.get('impact') or 'Protects HTTPS availability and certificate governance readiness.'
                    ),
                    'visible_in': ['Recommendations', 'Kubernetes TLS Secret', 'TLS Secret Update', 'Reports'],
                    'evidence': {
                        'cluster_id': str(cluster_id),
                        'namespace': str(namespace_label),
                        'affected_count': int(count),
                        'status': status_value,
                        'example_secret': example_secret,
                        'issuer': issuer,
                        'days_remaining': days_remaining if days_remaining is not None else min_days_remaining,
                        'affected_hosts': ', '.join(affected_hosts),
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
