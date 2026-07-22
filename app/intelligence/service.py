from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy import func
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.intelligence.catalog import INTELLIGENCE_CATALOG

PER_PAGE_OPTIONS = [5, 10, 25, 50]

DOMAIN_OPTIONS = [
    {'value': '', 'label': 'All Asset Domains'},
    {'value': 'kubernetes', 'label': 'Kubernetes'},
    {'value': 'server', 'label': 'Server'},
    {'value': 'hci', 'label': 'HCI'},
]
CATEGORY_OPTIONS = [
    {'value': '', 'label': 'All Categories'},
    {'value': 'capacity', 'label': 'Capacity'},
    {'value': 'governance', 'label': 'Governance'},
    {'value': 'reliability', 'label': 'Reliability'},
    {'value': 'operations', 'label': 'Operations'},
    {'value': 'optimization', 'label': 'Optimization'},
    {'value': 'performance', 'label': 'Performance'},
]
SEVERITY_OPTIONS = [
    {'value': '', 'label': 'All Severities'},
    {'value': 'critical', 'label': 'Critical'},
    {'value': 'warning', 'label': 'Warning'},
    {'value': 'info', 'label': 'Info'},
]
STATUS_OPTIONS = [
    {'value': '', 'label': 'All Statuses'},
    {'value': 'available', 'label': 'Ready'},
    {'value': 'reserved', 'label': 'Integration Scope'},
    {'value': 'imported_signal', 'label': 'Imported Signal'},
]
SOURCE_KIND_OPTIONS = [
    {'value': '', 'label': 'All Resource Types'},
    {'value': 'cluster', 'label': 'Cluster'},
    {'value': 'node', 'label': 'Node'},
    {'value': 'namespace', 'label': 'Namespace'},
    {'value': 'workload', 'label': 'Workload'},
    {'value': 'pod', 'label': 'Pod'},
    {'value': 'persistent_volume', 'label': 'Persistent Volume'},
    {'value': 'tls_secret', 'label': 'TLS Secret'},
    {'value': 'vm', 'label': 'VM'},
    {'value': 'datastore', 'label': 'Datastore'},
    {'value': 'hci_cluster', 'label': 'HCI Cluster'},
]
LOGIC_TYPE_OPTIONS = [
    {'value': '', 'label': 'All Logic Types'},
    {'value': 'recommendation', 'label': 'Recommendation'},
    {'value': 'governance_check', 'label': 'Governance Check'},
    {'value': 'forecast_insight', 'label': 'Forecast Insight'},
    {'value': 'alert_enrichment', 'label': 'Alert Enrichment'},
    {'value': 'operational_hygiene', 'label': 'Operational Hygiene'},
]
SIGNAL_SOURCE_OPTIONS = [
    {'value': '', 'label': 'All Signal Sources'},
    {'value': 'kubernetes_api', 'label': 'Kubernetes API'},
    {'value': 'kaori_kubernetes_analysis', 'label': 'KAORI Kubernetes Analysis'},
    {'value': 'alertmanager', 'label': 'Alertmanager'},
    {'value': 'prometheus_metrics', 'label': 'Prometheus Metrics'},
    {'value': 'server_inventory', 'label': 'Server Node Exporter'},
    {'value': 'hci_provider_api', 'label': 'HCI API'},
]


def _clean(value: str | None) -> str:
    return (value or '').strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_int(value: str | None, default: int) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _format_label(value: str) -> str:
    return value.replace('_', ' ').title()


def _domain_label(value: str) -> str:
    return {'kubernetes': 'Kubernetes', 'server': 'Server', 'hci': 'HCI'}.get(value, _format_label(value))


def _status_label(value: str) -> str:
    return {
        'available': 'Ready',
        'reserved': 'Integration Scope',
        'imported_signal': 'Imported Signal',
    }.get(value, _format_label(value))


def _signal_label(value: str) -> str:
    return {
        'kubernetes_api': 'Kubernetes API',
        'kaori_kubernetes_analysis': 'KAORI Kubernetes Analysis',
        'alertmanager': 'Alertmanager',
        'prometheus_metrics': 'Prometheus Metrics',
        'server_inventory': 'Server Node Exporter',
        'hci_provider_api': 'HCI API',
    }.get(value, _format_label(value))


def _logic_label(value: str) -> str:
    return {
        'recommendation': 'Recommendation',
        'governance_check': 'Governance Check',
        'forecast_insight': 'Forecast Insight',
        'alert_enrichment': 'Alert Enrichment',
        'operational_hygiene': 'Operational Hygiene',
    }.get(value, _format_label(value))


def _normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    domain = str(rule['domain'])
    status = str(rule['status'])
    severity = str(rule['severity'])
    category = str(rule['category'])
    source_kind = str(rule['source_kind'])
    logic_type = str(rule.get('logic_type', 'recommendation'))
    signal_source = str(rule.get('signal_source', 'kaori_kubernetes_analysis'))
    return {
        **rule,
        'domain_label': _domain_label(domain),
        'status_label': _status_label(status),
        'severity_label': _format_label(severity),
        'category_label': _format_label(category),
        'source_kind_label': _format_label(source_kind),
        'logic_type_label': _logic_label(logic_type),
        'signal_source_label': _signal_label(signal_source),
        'tone': {
            'critical': 'red',
            'warning': 'amber',
            'info': 'blue',
        }.get(severity, 'slate'),
        'status_tone': {
            'available': 'emerald',
            'reserved': 'amber',
            'imported_signal': 'purple',
        }.get(status, 'slate'),
    }


def _matches(rule: dict[str, Any], filters: dict[str, str]) -> bool:
    """Apply dropdown and search filters consistently for Catalog and Recommendations."""

    for key in ['domain', 'category', 'severity', 'status', 'source_kind', 'logic_type', 'signal_source']:
        selected = _clean(filters.get(key))
        current_value = _clean(str(rule.get(key, '')))
        if selected and current_value != selected:
            return False

    query = _clean(filters.get('q')).lower()
    if query:
        evidence = rule.get('evidence')
        evidence_text = (
            ' '.join(f'{key} {value}' for key, value in evidence.items()) if isinstance(evidence, dict) else ''
        )
        fix_steps = rule.get('fix_steps')
        fix_steps_text = ' '.join(str(step) for step in fix_steps) if isinstance(fix_steps, list) else ''

        haystack = ' '.join(
            [
                str(rule.get(field, ''))
                for field in [
                    'rule_key',
                    'title',
                    'summary',
                    'condition_summary',
                    'recommended_action',
                    'impact',
                    'prometheus_relationship',
                    'affected_summary',
                    'domain_label',
                    'category_label',
                    'severity_label',
                    'status_label',
                    'source_kind_label',
                    'logic_type_label',
                    'signal_source_label',
                ]
            ]
            + [evidence_text, fix_steps_text]
        ).lower()
        if query not in haystack:
            return False

    return True


def _base_payload(args: MultiDict[str, str], *, page_mode: str) -> dict[str, Any]:
    filters = {
        'domain': _clean(args.get('domain')),
        'category': _clean(args.get('category')),
        'severity': _clean(args.get('severity')),
        'status': _clean(args.get('status')),
        'source_kind': _clean(args.get('source_kind')),
        'logic_type': _clean(args.get('logic_type')),
        'signal_source': _clean(args.get('signal_source')),
        'q': _clean(args.get('q')),
    }

    per_page = _to_int(args.get('per_page'), 5)
    if per_page not in PER_PAGE_OPTIONS:
        per_page = 5

    page = max(_to_int(args.get('page'), 1), 1)

    catalog = [_normalize_rule(rule) for rule in INTELLIGENCE_CATALOG]
    source_items = catalog if page_mode == 'catalog' else get_active_recommendation_findings()
    filtered = [rule for rule in source_items if _matches(rule, filters)]
    total_items = len(filtered)
    total_pages = max(ceil(total_items / per_page), 1)
    page = min(page, total_pages)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    items = filtered[start_index:end_index]

    start_item = start_index + 1 if total_items else 0
    end_item = min(end_index, total_items) if total_items else 0
    item_label = 'catalog rules' if page_mode == 'catalog' else 'recommendations'

    return {
        'page_mode': page_mode,
        'filters': filters,
        'filter_options': {
            'domains': DOMAIN_OPTIONS,
            'categories': CATEGORY_OPTIONS,
            'severities': SEVERITY_OPTIONS,
            'statuses': STATUS_OPTIONS,
            'source_kinds': SOURCE_KIND_OPTIONS,
            'logic_types': LOGIC_TYPE_OPTIONS,
            'signal_sources': SIGNAL_SOURCE_OPTIONS,
            'per_page': PER_PAGE_OPTIONS,
        },
        'items': items,
        'catalog': catalog,
        'recommendation_findings': source_items if page_mode != 'catalog' else [],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total_items,
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

    findings = [_normalize_rule(finding) for finding in findings]
    for finding in findings:
        finding.setdefault('affected_summary', _format_affected_summary(finding))
        finding.setdefault('affected_items', _build_affected_items(finding))
        finding.setdefault('fix_steps', _build_fix_steps(finding))
    findings.sort(key=lambda item: (_severity_rank(str(item.get('severity'))), str(item.get('title', ''))))
    return findings


def get_active_recommendation_findings(
    *,
    selected_cluster_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return active catalog-backed findings for reusable product surfaces.

    This is the shared source used by Intelligence > Recommendations and the
    Dashboard Recommended Actions section. When a cluster is selected, only
    findings whose evidence belongs to that cluster are returned.
    """

    catalog = [_normalize_rule(rule) for rule in INTELLIGENCE_CATALOG]
    findings = _build_recommendation_findings(catalog)

    selected_cluster = _clean(selected_cluster_id)
    if selected_cluster:
        findings = [finding for finding in findings if _finding_cluster_id(finding) == selected_cluster]

    if limit is not None:
        findings = findings[: max(int(limit), 0)]

    return findings


def _finding_cluster_id(finding: dict[str, Any]) -> str:
    evidence = finding.get('evidence')
    if not isinstance(evidence, dict):
        return ''
    return _clean(str(evidence.get('cluster_id') or ''))


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
    output.setdefault('affected_summary', _format_affected_summary(output))
    output.setdefault('affected_items', _build_affected_items(output))
    output.setdefault('fix_steps', _build_fix_steps(output))
    return output


def _format_affected_summary(item: dict[str, Any]) -> str:
    evidence = _as_dict(item.get('evidence'))
    affected_count = evidence.get('affected_pods') or evidence.get('affected_count') or evidence.get('count')
    namespace = str(evidence.get('namespace') or '').strip()
    cluster_id = str(evidence.get('cluster_id') or '').strip()
    source_kind = str(item.get('source_kind_label') or item.get('source_kind') or 'Resource')

    if affected_count:
        location_parts = []
        if namespace and namespace != 'cluster scope':
            location_parts.append(f'namespace {namespace}')
        if cluster_id:
            location_parts.append(f'cluster {cluster_id}')
        location = ' in ' + ' / '.join(location_parts) if location_parts else ''
        return f'{affected_count} {source_kind.lower()} item(s){location} matched this recommendation rule.'

    domain = str(item.get('domain_label') or item.get('domain') or 'asset')
    return f'{source_kind} item in {domain} scope matched this recommendation rule.'


def _build_affected_items(item: dict[str, Any]) -> list[dict[str, str]]:
    evidence = _as_dict(item.get('evidence'))
    source_kind = str(item.get('source_kind_label') or item.get('source_kind') or 'Resource')
    output: list[dict[str, str]] = [
        {'label': 'Asset', 'value': str(item.get('domain_label') or item.get('domain') or '-')},
        {'label': 'Resource', 'value': source_kind},
    ]

    cluster_id = str(evidence.get('cluster_id') or '').strip()
    namespace = str(evidence.get('namespace') or '').strip()
    count = evidence.get('affected_pods') or evidence.get('affected_count') or evidence.get('count')
    phase = str(evidence.get('phase') or '').strip()
    status = str(evidence.get('status') or '').strip()
    secret_name = str(evidence.get('secret_name') or evidence.get('example_secret') or '').strip()
    days_remaining = evidence.get('days_remaining') or evidence.get('min_days_remaining')
    issuer = str(evidence.get('issuer') or '').strip()

    if cluster_id:
        output.append({'label': 'Cluster', 'value': cluster_id})
    if namespace:
        output.append({'label': 'Namespace', 'value': namespace})
    if count:
        output.append({'label': 'Affected', 'value': str(count)})
    if phase:
        output.append({'label': 'Phase', 'value': phase})
    if status:
        output.append({'label': 'Status', 'value': status})
    if secret_name:
        output.append({'label': 'TLS Secret', 'value': secret_name})
    if days_remaining is not None:
        output.append({'label': 'Days Remaining', 'value': str(days_remaining)})
    if issuer:
        output.append({'label': 'Issuer', 'value': issuer})

    return output[:8]


def _build_fix_steps(item: dict[str, Any]) -> list[str]:
    source_kind = str(item.get('source_kind') or '')
    category = str(item.get('category') or '')
    action = str(item.get('recommended_action') or '').strip()
    steps: list[str] = []

    if action:
        steps.append(action)

    if source_kind == 'pod':
        steps.extend(
            [
                'Open Pod Inventory or the related workload page and inspect events, restarts, image pull state, probes, and node placement.',
                'Apply the manifest/configuration fix, restart or roll out the affected workload, then resync inventory to confirm the finding is cleared.',
            ]
        )
    elif source_kind == 'node':
        steps.extend(
            [
                'Open Node Inventory and check kubelet, container runtime, disk pressure, memory pressure, network reachability, and recent node events.',
                'Recover or cordon/drain the node as needed, then resync inventory and validate schedulable capacity.',
            ]
        )
    elif source_kind == 'persistent_volume':
        steps.extend(
            [
                'Open Storage Analysis and review PVC/PV status, storage class, provisioner health, and the affected namespace/workload dependency.',
                'Fix binding/provisioning or expand/clean storage, then resync inventory and rerun the recommendation filter.',
            ]
        )
    elif source_kind == 'tls_secret':
        steps.extend(
            [
                'Open Governance > K8s Operation > Kubernetes TLS Secret and review the affected Secret, issuer, SAN coverage, expiry, and Ingress usage mapping.',
                'Use TLS Secret Update to upload the renewed tls.crt and tls.key, validate the selected existing Secret targets with HTMX preview, then update only the approved targets.',
                'Resync TLS inventory and validate the affected Ingress endpoints after the update completes.',
            ]
        )
    elif source_kind == 'workload':
        steps.extend(
            [
                'Open Workload Analysis and review requests, limits, rollout status, container images, and namespace policy context.',
                'Patch the workload manifest, roll out safely, then resync inventory to verify the rule no longer triggers.',
            ]
        )
    elif category == 'capacity':
        steps.extend(
            [
                'Review capacity trend and top consumers before changing limits, quotas, or infrastructure allocation.',
                'Apply the capacity action and validate the result through analytics and generated report context.',
            ]
        )
    else:
        steps.extend(
            [
                'Open the related inventory or analytics page shown under Visibility and validate the affected resource context.',
                'Apply the recommended remediation, then resync data sources to confirm the recommendation is resolved.',
            ]
        )

    deduped: list[str] = []
    for step in steps:
        if step and step not in deduped:
            deduped.append(step)
    return deduped[:4]


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
        rows = db.session.query(PodInventory).all()
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

    try:
        unhealthy_rows = (
            db.session.query(
                PodInventory.cluster_id,
                PodInventory.namespace,
                PodInventory.phase,
                func.count(PodInventory.id),
            )
            .filter(PodInventory.phase.notin_(['Running', 'Succeeded']))
            .group_by(PodInventory.cluster_id, PodInventory.namespace, PodInventory.phase)
            .all()
        )
        restart_rows = (
            db.session.query(
                PodInventory.cluster_id,
                PodInventory.namespace,
                func.count(PodInventory.id),
            )
            .filter(PodInventory.restart_count >= 5)
            .group_by(PodInventory.cluster_id, PodInventory.namespace)
            .all()
        )
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
                    summary=f'Pod inventory shows {count} pod{"s" if int(count) != 1 else ""} in phase {phase or "Unknown"}.',
                    condition_summary='Collected pod phase is not Running or Succeeded.',
                    evidence={
                        'cluster_id': str(cluster_id),
                        'namespace': str(namespace),
                        'affected_count': int(count),
                        'phase': str(phase or 'Unknown'),
                    },
                )
            )

    if restart_rule:
        for cluster_id, namespace, count in restart_rows:
            findings.append(
                _clone_rule_as_finding(
                    restart_rule,
                    finding_key=f'kubernetes.pod.high_restart_count:{cluster_id}:{namespace}',
                    title=f'{count} pod{"s" if int(count) != 1 else ""} in {namespace} have high restart count',
                    summary=f'Pod inventory shows {count} pod{"s" if int(count) != 1 else ""} with restart count at or above 5.',
                    condition_summary='Collected pod restart_count is greater than or equal to 5.',
                    evidence={
                        'cluster_id': str(cluster_id),
                        'namespace': str(namespace),
                        'affected_count': int(count),
                    },
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
        rows = (
            db.session.query(NodeInventory.cluster_id, func.count(NodeInventory.id))
            .filter(NodeInventory.status != 'Ready')
            .group_by(NodeInventory.cluster_id)
            .all()
        )
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
        rows = (
            db.session.query(
                StorageInventory.cluster_id,
                StorageInventory.namespace,
                StorageInventory.status,
                func.count(StorageInventory.id),
            )
            .filter(StorageInventory.status.notin_(['Bound', 'Available']))
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
            _normalize_rule(
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


def get_recommendations_payload(args: MultiDict[str, str], *, page_mode: str = 'recommendations') -> dict[str, Any]:
    payload = _base_payload(args, page_mode=page_mode)
    catalog = payload['catalog']

    kubernetes_count = sum(1 for rule in catalog if rule['domain'] == 'kubernetes')
    server_count = sum(1 for rule in catalog if rule['domain'] == 'server')
    hci_count = sum(1 for rule in catalog if rule['domain'] == 'hci')
    imported_count = sum(1 for rule in catalog if rule['status'] == 'imported_signal')
    ready_count = sum(1 for rule in catalog if rule['status'] == 'available')
    integration_count = sum(1 for rule in catalog if rule['status'] == 'reserved')

    is_catalog = page_mode == 'catalog'
    payload.update(
        {
            'page_title': 'Catalog' if is_catalog else 'Recommendations',
            'page_subtitle': (
                'Rule registry for Kubernetes, Server, and HCI intelligence domains.'
                if is_catalog
                else 'Actionable guidance from inventory state, metrics signals, alert context, and report readiness.'
            ),
            'hero_label': 'Infrastructure intelligence',
            'engine_status': 'Signal-based guidance',
            'engine_description': (
                'Evaluates inventory, metrics, alerts, and provider signals across Kubernetes, Server, and HCI assets.'
            ),
            'workspace_label': 'Recommendation rule catalog' if is_catalog else 'Actionable recommendation workspace',
            'workspace_description': (
                'Catalog lists rule definitions, signal sources, asset scope, detection logic, and visibility across report families.'
                if is_catalog
                else 'Recommendations show findings triggered by catalog rules against current inventory, metrics, alerts, and report context.'
            ),
            'workspace_action_label': 'Open Recommendations' if is_catalog else 'Open Catalog',
            'workspace_action_endpoint': 'intelligence.recommendations' if is_catalog else 'intelligence.catalog',
            'summary_cards': [
                {
                    'label': 'Kubernetes',
                    'value': kubernetes_count,
                    'caption': 'Prometheus + Alertmanager per cluster',
                    'icon': 'boxes',
                    'tone': 'green',
                },
                {
                    'label': 'Server',
                    'value': server_count,
                    'caption': 'Node Exporter metric scope',
                    'icon': 'server',
                    'tone': 'blue',
                },
                {
                    'label': 'HCI',
                    'value': hci_count,
                    'caption': 'HCI API integration scope',
                    'icon': 'network',
                    'tone': 'amber',
                },
                {
                    'label': 'Imported Signals',
                    'value': imported_count,
                    'caption': 'Alert and metric enrichment',
                    'icon': 'radio-tower',
                    'tone': 'purple',
                },
            ],
            'asset_cards': [
                {
                    'title': 'Kubernetes Intelligence',
                    'status': 'Ready',
                    'description': 'Uses Kubernetes inventory, Prometheus metrics, and Alertmanager signals per connected cluster.',
                    'icon': 'boxes',
                    'report_family': 'KAORI Kubernetes Reports',
                    'signal_source': 'Kubernetes API · Prometheus · Alertmanager',
                    'count': kubernetes_count,
                },
                {
                    'title': 'Server Intelligence',
                    'status': 'Integration Scope',
                    'description': 'Server recommendations are categorized for Node Exporter metrics and future server inventory context.',
                    'icon': 'server',
                    'report_family': 'KAORI Server Reports',
                    'signal_source': 'Node Exporter',
                    'count': server_count,
                },
                {
                    'title': 'HCI Intelligence',
                    'status': 'Integration Scope',
                    'description': 'HCI recommendations are categorized for provider API signals, datastore health, host balance, and VM placement.',
                    'icon': 'network',
                    'report_family': 'KAORI HCI Reports',
                    'signal_source': 'HCI API',
                    'count': hci_count,
                },
            ],
            'context_cards': [
                {
                    'title': 'Recommendations',
                    'description': 'Shows actionable guidance generated from rules, inventory, metrics, alert context, and report-readiness signals.',
                    'icon': 'sparkles',
                },
                {
                    'title': 'Catalog',
                    'description': 'Defines the rule registry: asset domain, condition, source, impact, status, and related report family.',
                    'icon': 'list-checks',
                },
                {
                    'title': 'Alert Intelligence',
                    'description': 'Enriches Prometheus and Alertmanager signals before they become investigation steps or recommendations.',
                    'icon': 'triangle-alert',
                },
            ],
            'ready_count': ready_count,
            'integration_count': integration_count,
        }
    )
    return payload


def get_alert_intelligence_payload() -> dict[str, Any]:
    return {
        'page_title': 'Alert Intelligence',
        'page_subtitle': 'Alert enrichment workspace for Prometheus, Alertmanager, Server, and HCI signals.',
        'hero_label': 'Alert signal intelligence',
        'engine_status': 'Enrichment ready',
        'engine_description': 'Prometheus detects, Alertmanager routes, Node Exporter and HCI API extend infrastructure context.',
        'boundaries': [
            {
                'title': 'Kubernetes alert path',
                'description': 'Prometheus owns metric detection and Alertmanager owns grouping, silence, routing, and notification per cluster.',
                'icon': 'activity',
            },
            {
                'title': 'Server signal path',
                'description': 'Node Exporter supplies server-level CPU, memory, disk, and network metrics for KAORI Server Reports intelligence.',
                'icon': 'server',
            },
            {
                'title': 'HCI signal path',
                'description': 'HCI API integration supplies datastore, host balance, cluster health, and VM placement context for KAORI HCI Reports intelligence.',
                'icon': 'network',
            },
        ],
        'dummy_flow': [
            {
                'step': '1',
                'title': 'Import signal',
                'description': 'Read Kubernetes alerts from Alertmanager, server metrics from Node Exporter, or HCI health from provider APIs.',
            },
            {
                'step': '2',
                'title': 'Map asset',
                'description': 'Classify the signal under Kubernetes, Server, or HCI and link it to the affected cluster, node, host, datastore, VM, or workload.',
            },
            {
                'step': '3',
                'title': 'Enrich context',
                'description': 'Attach ownership, inventory state, trend, capacity, related reports, and report-family context.',
            },
            {
                'step': '4',
                'title': 'Recommend action',
                'description': 'Produce investigation guidance without replacing Prometheus rules or Alertmanager routing policy.',
            },
        ],
    }
