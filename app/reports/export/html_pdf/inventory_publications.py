from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

_PAGE_COUNT = 9
_UNAVAILABLE = {'', '-', 'n/a', 'none', 'not available', 'not reported', 'unknown'}


def _field(label: str, key: str) -> dict[str, str]:
    return {'label': label, 'key': key}


_PROFILES: dict[str, dict[str, Any]] = {
    'inventory_overview': {
        'title': 'Inventory Overview',
        'template': 'reports/pdf/inventory_overview.html',
        'purpose': 'Support management review of committed Kubernetes asset counts, node readiness, resource composition, inventory freshness, and accountable follow-up actions.',
        'context': 'The overview summarizes the latest committed inventory generation. Detailed identities and relationships remain in the dedicated inventory publications.',
        'asset_label': 'Inventory Assets',
        'primary_fields': [_field('Resource', 'resource_type'), _field('Count', 'assets'), _field('Status', 'status')],
        'evidence_fields': [
            _field('Cluster Count', 'clusters'),
            _field('Node Count', 'nodes'),
            _field('Namespace Count', 'namespaces'),
            _field('Workload Count', 'workloads'),
            _field('Pod Count', 'pods'),
            _field('Service Count', 'services'),
            _field('Ingress Count', 'ingresses'),
            _field('Configuration Count', 'configuration'),
            _field('Storage Count', 'storage'),
        ],
        'relationship_filters': ('Namespace', 'Workload', 'Pod', 'Service', 'Ingress', 'Storage'),
        'detail_pages': [
            ('Resource Composition', 'Committed Kubernetes resource totals across the selected inventory boundary.'),
            ('Node Readiness', 'Committed node readiness and participation evidence.'),
            ('Workload and Pod Coverage', 'Committed workload, pod, and namespace coverage.'),
            ('Network and Storage Counts', 'Committed service, ingress, configuration, and storage totals.'),
            ('Inventory Health and Freshness', 'Publication coverage, freshness, and source-state interpretation.'),
        ],
        'recommendations': [
            ('Maintain Inventory Freshness', 'Platform Operations'),
            ('Preserve Complete Asset Coverage', 'Platform Operations'),
            ('Validate Detailed Inventory Registers', 'Platform Operations'),
        ],
        'included': [
            'Committed cluster and Kubernetes resource counts.',
            'Committed node readiness summary.',
            'Inventory collection time, scope, and publication coverage.',
        ],
        'excluded': [
            'Live changes after the committed data cut-off.',
            'Detailed identities not present in the selected snapshot.',
            'Runtime health, utilization, security, and ownership conclusions.',
        ],
    },
    'node_inventory': {
        'title': 'Nodes Inventory',
        'template': 'reports/pdf/nodes_inventory.html',
        'purpose': 'Support operational review of node identity, role, readiness, scheduling participation, platform metadata, pressure conditions, and accountable node actions.',
        'context': 'Node readiness is inventory evidence, not a substitute for capacity, utilization, or live condition validation.',
        'asset_label': 'Nodes',
        'primary_fields': [
            _field('Node', 'node'), _field('Role', 'role'), _field('Status', 'status'),
            _field('CPU', 'cpu'), _field('Memory', 'memory'), _field('Kubelet', 'kubelet_version'),
        ],
        'evidence_fields': [
            _field('Node Identity', 'node'), _field('Role', 'role'), _field('Readiness', 'status'),
            _field('Scheduling State', 'unschedulable'), _field('Kubelet Version', 'kubelet_version'),
            _field('Container Runtime', 'container_runtime'), _field('Memory Pressure', 'memory_pressure'),
            _field('Disk Pressure', 'disk_pressure'), _field('Internal IP', 'internal_ip'),
        ],
        'relationship_filters': ('Node',),
        'detail_pages': [
            ('Node Inventory', 'Committed node identity, role, capacity, and platform metadata.'),
            ('Lifecycle and Status', 'Readiness, schedulability, pressure conditions, and lifecycle evidence.'),
            ('Relationship Coverage', 'Node participation in pod placement and cluster topology.'),
            ('Governance and Risk Evidence', 'Version, taint, maintenance, and ownership evidence.'),
            ('Inventory Evidence Register', 'Source freshness, coverage, and publication readiness.'),
        ],
        'recommendations': [
            ('Review Not Ready or Unschedulable Nodes', 'Platform Operations'),
            ('Validate Node Version and Runtime Baseline', 'Platform Operations'),
            ('Maintain Node Condition Evidence', 'Observability Owner'),
        ],
        'included': [
            'Committed node identity, role, readiness, capacity, version, runtime, and address fields.',
            'Committed node pressure and schedulability fields when available.',
            'Committed pod-to-node relationship counts.',
        ],
        'excluded': [
            'Live node conditions after the report cut-off.',
            'Uncommitted maintenance windows and ownership assignments.',
            'Utilization and capacity conclusions that require analytics evidence.',
        ],
    },
    'namespace_inventory': {
        'title': 'Namespaces Inventory',
        'template': 'reports/pdf/namespaces_inventory.html',
        'purpose': 'Support governance review of namespace identity, lifecycle state, labels, controls, service-account posture, resource relationships, and accountable namespace actions.',
        'context': 'Namespace presence does not establish ownership, quota coverage, or policy compliance without committed supporting evidence.',
        'asset_label': 'Namespaces',
        'primary_fields': [
            _field('Namespace', 'namespace'), _field('Status', 'status'), _field('LimitRanges', 'limit_ranges'),
            _field('NetworkPolicies', 'network_policies'), _field('ServiceAccounts', 'service_accounts'),
            _field('Default SA', 'default_service_account'),
        ],
        'evidence_fields': [
            _field('Namespace Identity', 'namespace'), _field('Lifecycle Status', 'status'),
            _field('Labels', 'labels'), _field('Annotations', 'annotations'),
            _field('LimitRange Count', 'limit_ranges'), _field('NetworkPolicy Count', 'network_policies'),
            _field('ServiceAccount Count', 'service_accounts'), _field('Default ServiceAccount', 'default_service_account'),
        ],
        'relationship_filters': ('Namespace',),
        'detail_pages': [
            ('Namespace Inventory', 'Committed namespace identity, status, and control counts.'),
            ('Lifecycle and Status', 'Namespace phase, creation evidence, and lifecycle interpretation.'),
            ('Relationship Coverage', 'Namespace relationships to workloads, pods, network, and storage resources.'),
            ('Governance and Risk Evidence', 'LimitRange, NetworkPolicy, service-account, and ownership evidence.'),
            ('Inventory Evidence Register', 'Source freshness, coverage, and publication readiness.'),
        ],
        'recommendations': [
            ('Review Inactive or Terminating Namespaces', 'Platform Operations'),
            ('Validate Namespace Control Coverage', 'Application Owner'),
            ('Confirm Namespace Ownership', 'Application Owner'),
        ],
        'included': [
            'Committed namespace identity, lifecycle status, labels, and annotations.',
            'Committed LimitRange, NetworkPolicy, and service-account counts.',
            'Committed namespace relationship counts.',
        ],
        'excluded': [
            'Live namespace changes after the report cut-off.',
            'ResourceQuota content not present in the namespace inventory row.',
            'Uncommitted application ownership and policy-compliance conclusions.',
        ],
    },
    'workload_inventory': {
        'title': 'Workloads Inventory',
        'template': 'reports/pdf/workloads_inventory.html',
        'purpose': 'Support operational review of workload identity, controller type, readiness, rollout state, namespace placement, relationships, and accountable workload actions.',
        'context': 'Workload inventory describes controller state at the committed cut-off and does not authorize scaling or configuration changes.',
        'asset_label': 'Workloads',
        'primary_fields': [
            _field('Workload', 'name'), _field('Namespace', 'namespace'), _field('Type', 'resource_type'),
            _field('Ready', 'ready'), _field('Status', 'status'), _field('Strategy', 'update_strategy'),
        ],
        'evidence_fields': [
            _field('Workload Identity', 'name'), _field('Namespace', 'namespace'), _field('Controller Type', 'resource_type'),
            _field('Readiness', 'ready'), _field('Runtime Status', 'status'), _field('Update Strategy', 'update_strategy'),
            _field('Desired Replicas', 'desired_replicas'), _field('Available Replicas', 'available_replicas'),
            _field('Updated Replicas', 'updated_replicas'),
        ],
        'relationship_filters': ('Workload',),
        'detail_pages': [
            ('Workload Inventory', 'Committed workload identity, controller type, readiness, and strategy.'),
            ('Lifecycle and Status', 'Replica, rollout, readiness, and controller-state evidence.'),
            ('Relationship Coverage', 'Workload relationships to pods, namespaces, services, and configuration.'),
            ('Governance and Risk Evidence', 'Owner, resource-governance, rollout, and configuration evidence.'),
            ('Inventory Evidence Register', 'Source freshness, coverage, and publication readiness.'),
        ],
        'recommendations': [
            ('Review Workloads With Incomplete Readiness', 'Application Owner'),
            ('Validate Controller Type and Update Strategy', 'Application Owner'),
            ('Maintain Workload Relationship Evidence', 'Platform Operations'),
        ],
        'included': [
            'Committed workload identity, namespace, controller type, readiness, status, and strategy.',
            'Committed replica fields when present in workload details.',
            'Committed workload-to-pod relationship counts.',
        ],
        'excluded': [
            'Live rollout state after the report cut-off.',
            'Resource requests, limits, and observed utilization.',
            'Uncommitted service ownership and deployment intent.',
        ],
    },
    'pod_inventory': {
        'title': 'Pods Inventory',
        'template': 'reports/pdf/pods_inventory.html',
        'purpose': 'Support operational review of pod identity, phase, readiness, node placement, restarts, images, workload ownership, configuration references, and accountable pod actions.',
        'context': 'Pod state is a committed snapshot. Live validation is required before deletion, restart, or rescheduling.',
        'asset_label': 'Pods',
        'primary_fields': [
            _field('Pod', 'pod'), _field('Namespace', 'namespace'), _field('Phase', 'status'),
            _field('Ready', 'ready'), _field('Node', 'node'), _field('Restarts', 'restarts'),
        ],
        'evidence_fields': [
            _field('Pod Identity', 'pod'), _field('Namespace', 'namespace'), _field('Phase', 'status'),
            _field('Readiness', 'ready'), _field('Node Placement', 'node'), _field('Restart Count', 'restarts'),
            _field('Workload Owner', 'workload'), _field('Container Count', 'container_count'),
            _field('Image Count', 'image_count'), _field('PVC References', 'persistent_volume_claims'),
        ],
        'relationship_filters': ('Pod',),
        'detail_pages': [
            ('Pod Inventory', 'Committed pod identity, namespace, phase, readiness, placement, and restart evidence.'),
            ('Lifecycle and Status', 'Pod phase, readiness, restart, container, and QoS evidence.'),
            ('Relationship Coverage', 'Pod relationships to workloads, nodes, configuration, and storage claims.'),
            ('Governance and Risk Evidence', 'Restart, image, configuration, storage, and ownership evidence.'),
            ('Inventory Evidence Register', 'Source freshness, coverage, and publication readiness.'),
        ],
        'recommendations': [
            ('Review Pending Failed or Restarting Pods', 'Application Owner'),
            ('Validate Pod Placement and Workload Ownership', 'Platform Operations'),
            ('Maintain Container and Configuration Evidence', 'Platform Operations'),
        ],
        'included': [
            'Committed pod identity, phase, readiness, placement, and restart count.',
            'Committed workload, image, configuration, and PVC reference counts.',
            'Committed pod relationship counts.',
        ],
        'excluded': [
            'Live pod state after the report cut-off.',
            'Container logs, events, and uncommitted termination reasons.',
            'Security-compliance conclusions without policy evidence.',
        ],
    },
    'service_inventory': {
        'title': 'Services Inventory',
        'template': 'reports/pdf/services_inventory.html',
        'purpose': 'Support network inventory review of service identity, type, addresses, ports, selectors, exposure, backend relationships, and accountable service actions.',
        'context': 'Service presence does not establish endpoint readiness or approved external exposure without committed backend evidence.',
        'asset_label': 'Services',
        'primary_fields': [
            _field('Service', 'name'), _field('Namespace', 'namespace'), _field('Type', 'resource_type'),
            _field('Cluster IP', 'cluster_ip'), _field('External IP', 'external_ip'), _field('Ports', 'ports'),
        ],
        'evidence_fields': [
            _field('Service Identity', 'name'), _field('Namespace', 'namespace'), _field('Service Type', 'resource_type'),
            _field('Cluster IP', 'cluster_ip'), _field('External IP', 'external_ip'), _field('Ports', 'ports'),
            _field('Selector Count', 'selector_count'), _field('Selector Detail', 'selector'),
            _field('Load Balancer', 'load_balancer'),
        ],
        'relationship_filters': ('Service',),
        'detail_pages': [
            ('Service Inventory', 'Committed service identity, type, addresses, ports, and selector evidence.'),
            ('Lifecycle and Status', 'Service publication, external address, and load-balancer evidence.'),
            ('Relationship Coverage', 'Service relationships to selectors, workloads, pods, and ingresses.'),
            ('Governance and Risk Evidence', 'Exposure, port, selector, annotation, and ownership evidence.'),
            ('Inventory Evidence Register', 'Source freshness, coverage, and publication readiness.'),
        ],
        'recommendations': [
            ('Review Externally Exposed Services', 'Platform Operations'),
            ('Validate Service Ports and Selectors', 'Application Owner'),
            ('Confirm Backend Endpoint Readiness', 'Platform Operations'),
        ],
        'included': [
            'Committed service identity, type, addresses, ports, and selector fields.',
            'Committed service relationship counts.',
            'Committed inventory scope and freshness.',
        ],
        'excluded': [
            'Live endpoint readiness after the report cut-off.',
            'Uncommitted firewall, load-balancer, and DNS state.',
            'Application ownership and exposure approval not present in inventory.',
        ],
    },
    'ingress_inventory': {
        'title': 'Ingresses Inventory',
        'template': 'reports/pdf/ingresses_inventory.html',
        'purpose': 'Support ingress review of identity, class, host, address, backend paths, TLS posture, routing relationships, and accountable ingress actions.',
        'context': 'Ingress TLS status describes committed configuration and does not establish certificate validity or backend health.',
        'asset_label': 'Ingresses',
        'primary_fields': [
            _field('Ingress', 'name'), _field('Namespace', 'namespace'), _field('Class', 'ingress_class'),
            _field('Host', 'host'), _field('Address', 'address'), _field('TLS', 'status'),
        ],
        'evidence_fields': [
            _field('Ingress Identity', 'name'), _field('Namespace', 'namespace'), _field('Ingress Class', 'ingress_class'),
            _field('Host', 'host'), _field('Address', 'address'), _field('TLS State', 'status'),
            _field('Backend Count', 'backend_count'), _field('TLS Secret Count', 'tls_secret_count'),
        ],
        'relationship_filters': ('Ingress',),
        'detail_pages': [
            ('Ingress Inventory', 'Committed ingress identity, class, host, address, backend, and TLS evidence.'),
            ('Lifecycle and Status', 'Ingress publication, address, class, and routing-state evidence.'),
            ('Relationship Coverage', 'Ingress relationships to hosts, paths, service backends, and TLS secrets.'),
            ('Governance and Risk Evidence', 'TLS, exposure, routing, certificate, and ownership evidence.'),
            ('Inventory Evidence Register', 'Source freshness, coverage, and publication readiness.'),
        ],
        'recommendations': [
            ('Review Ingresses Without TLS', 'Platform Operations'),
            ('Validate Host Path and Backend Mapping', 'Application Owner'),
            ('Confirm Certificate and Ownership Readiness', 'Platform Operations'),
        ],
        'included': [
            'Committed ingress identity, namespace, class, host, address, and TLS state.',
            'Committed backend and TLS-secret counts when available.',
            'Committed ingress relationship counts.',
        ],
        'excluded': [
            'Live controller and backend state after the report cut-off.',
            'Certificate expiry and issuer evidence outside the ingress row.',
            'Uncommitted DNS, firewall, and application-owner conclusions.',
        ],
    },
    'storage_inventory': {
        'title': 'Storage Inventory',
        'template': 'reports/pdf/storage_inventory.html',
        'purpose': 'Support storage inventory review of identity, type, class, capacity, lifecycle, claim, provisioner, access mode, and accountable storage actions.',
        'context': 'Storage object presence does not establish free capacity, workload safety, or lifecycle approval without committed claim and utilization evidence.',
        'asset_label': 'Storage Assets',
        'primary_fields': [
            _field('Storage Asset', 'name'), _field('Namespace', 'namespace'), _field('Type', 'resource_type'),
            _field('Class', 'storage_class'), _field('Capacity', 'capacity'), _field('Status', 'status'),
        ],
        'evidence_fields': [
            _field('Storage Identity', 'name'), _field('Namespace', 'namespace'), _field('Storage Type', 'resource_type'),
            _field('Storage Class', 'storage_class'), _field('Capacity', 'capacity'), _field('Lifecycle Status', 'status'),
            _field('Access Modes', 'access_modes'), _field('Reclaim Policy', 'reclaim_policy'),
            _field('Claim Name', 'claim_name'), _field('Provisioner', 'provisioner'),
        ],
        'relationship_filters': ('Storage', 'PVC'),
        'detail_pages': [
            ('Persistent Volume Inventory', 'Committed storage identity, type, class, capacity, and lifecycle evidence.'),
            ('Lifecycle and Status', 'Binding, phase, access mode, reclaim, and volume-mode evidence.'),
            ('Relationship Coverage', 'Storage relationships to PVCs, namespaces, workloads, and storage classes.'),
            ('Governance and Risk Evidence', 'Capacity, lifecycle, reclaim, provisioner, and ownership evidence.'),
            ('Inventory Evidence Register', 'Source freshness, coverage, and publication readiness.'),
        ],
        'recommendations': [
            ('Review Unbound or Non Ready Storage Assets', 'Platform Operations'),
            ('Validate Capacity Class and Reclaim Policy', 'Platform Operations'),
            ('Confirm Claim and Workload Relationships', 'Application Owner'),
        ],
        'included': [
            'Committed storage identity, type, class, capacity, and lifecycle status.',
            'Committed access mode, reclaim, claim, and provisioner fields when available.',
            'Committed storage and PVC relationship counts.',
        ],
        'excluded': [
            'Live utilization and free-capacity state after the report cut-off.',
            'Uncommitted backup, data-protection, and application-owner evidence.',
            'Lifecycle authorization and deletion safety conclusions.',
        ],
    },
    'topology_inventory': {
        'title': 'Kubernetes Topology',
        'template': 'reports/pdf/topology_inventory.html',
        'purpose': 'Support review of committed cluster, namespace, node, workload, pod, network, configuration, and storage relationships across the Kubernetes topology.',
        'context': 'Topology edges are published only when a committed relationship can be derived from inventory fields. Aggregate counts never create synthetic edges.',
        'asset_label': 'Topology Assets',
        'primary_fields': [_field('Resource', 'resource_type'), _field('Count', 'assets'), _field('Status', 'status')],
        'evidence_fields': [
            _field('Cluster Count', 'clusters'), _field('Node Count', 'nodes'), _field('Namespace Count', 'namespaces'),
            _field('Workload Count', 'workloads'), _field('Pod Count', 'pods'), _field('Service Count', 'services'),
            _field('Ingress Count', 'ingresses'), _field('Storage Count', 'storage'),
        ],
        'relationship_filters': ('Namespace', 'Workload', 'Pod', 'Node', 'Service', 'Ingress', 'Storage', 'PVC', 'Configuration'),
        'detail_pages': [
            ('Cluster Topology', 'Committed cluster, node, and namespace composition.'),
            ('Namespace Topology', 'Namespace relationships to workloads, pods, services, ingresses, and storage.'),
            ('Workload and Pod Topology', 'Workload-to-pod and pod-to-node relationship evidence.'),
            ('Network and Storage Topology', 'Ingress, service, configuration, and storage relationship evidence.'),
            ('Topology Evidence Register', 'Source freshness, edge coverage, and graph publication readiness.'),
        ],
        'recommendations': [
            ('Maintain Resource Identity Coverage', 'Platform Operations'),
            ('Review Missing Relationship Edges', 'Platform Operations'),
            ('Validate Network and Storage Dependencies', 'Application Owner'),
        ],
        'included': [
            'Committed resource counts and inventory identities.',
            'Relationship counts derived from committed inventory fields.',
            'Committed collection scope and freshness.',
        ],
        'excluded': [
            'Synthetic graph edges inferred from aggregate totals.',
            'Live runtime dependency state after the report cut-off.',
            'Uncommitted ownership, traffic flow, and business-criticality relationships.',
        ],
    },
}

_TEMPLATE_BY_REPORT_TYPE = {key: value['template'] for key, value in _PROFILES.items()}


def inventory_template_for_report_type(report_type: str) -> str:
    return _TEMPLATE_BY_REPORT_TYPE.get(report_type, 'reports/pdf/inventory_overview.html')


def build_inventory_publication_presentation(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> dict[str, Any]:
    report_type = sanitize_text(getattr(report, 'report_type', ''), fallback='inventory_overview')
    profile = _PROFILES.get(report_type, _PROFILES['inventory_overview'])
    rows = [_mapping(item) for item in _sequence(payload.get('inventory_assets'))]
    rows = [dict(item) for item in rows]
    overview = dict(_mapping(payload.get('inventory_overview')))
    summary = _mapping(payload.get('inventory_summary') or payload.get('summary'))
    distribution = _mapping(payload.get('inventory_distribution'))
    status_rows = _distribution_rows(distribution.get('by_status'), 'status')
    type_rows = _distribution_rows(distribution.get('by_type'), 'resource_type')
    cluster_rows = _distribution_rows(distribution.get('by_cluster'), 'cluster')
    topology_rows = _topology_rows(payload, profile)
    evidence_rows = _evidence_rows(profile, rows, overview)
    total_assets = _int(summary.get('total_assets')) or sum(_int(item.get('assets')) for item in rows)
    distinct_statuses = _int(summary.get('distinct_statuses')) or len(status_rows)
    distinct_types = _int(summary.get('distinct_types')) or len(type_rows)
    collected_at = _display(payload.get('collected_at') or summary.get('collected_at'), fallback=data_cutoff)
    environment = sanitize_text(_mapping(payload.get('cluster')).get('environment'), fallback='Not Available')

    executive_metrics = _executive_metrics(report_type, profile, rows, overview, summary, topology_rows)
    executive_rows = _table_rows(rows, profile['primary_fields'], limit=5)
    if not executive_rows:
        executive_rows = [['No committed inventory rows', 'Not Available', 'Review']]

    detail_pages = _build_detail_pages(
        report_type,
        profile,
        rows,
        overview,
        status_rows,
        type_rows,
        cluster_rows,
        topology_rows,
        evidence_rows,
        total_assets,
        collected_at,
    )
    recommendations = _recommendations(profile, rows, evidence_rows, topology_rows)

    return {
        'presentation_version': f'v1.1-{report_type.replace("_", "-")}-publication',
        'page_count': _PAGE_COUNT,
        'layout_contract': {
            'paper': 'A4 Portrait',
            'page_count': 9,
            'fixed_page_canvas': True,
            'table_policy': 'single-line-technical-registers',
            'inventory_policy': 'latest-committed-generation',
            'relationship_policy': 'committed-edges-only',
            'missing_evidence_policy': 'explicit-not-available',
            'visual_style': 'kaori-publication-standard-v1.0',
        },
        'report_id': report_id,
        'report_name': report_name,
        'report_title': profile['title'],
        'report_type': report_type,
        'cluster_scope': cluster_scope,
        'namespace_scope': namespace_scope,
        'period_label': period_label,
        'data_cutoff': data_cutoff,
        'generated_at': generated_at,
        'generated_by': generated_by,
        'classification': classification,
        'cover': {
            'environment': environment,
            'purpose': profile['purpose'],
            'context': profile['context'],
        },
        'executive': {
            'metrics': executive_metrics,
            'title': _executive_title(report_type),
            'subtitle': 'Management position for committed Kubernetes inventory at the report cut-off.',
            'table_title': 'Committed Inventory Position',
            'table_subtitle': 'Leading asset records or aggregate resource counts from the committed generation.',
            'columns': [item['label'] for item in profile['primary_fields']],
            'rows': executive_rows,
            'interpretation_title': _interpretation_title(report_type, total_assets, topology_rows),
            'interpretation_body': _interpretation_body(report_type, total_assets, distinct_statuses, distinct_types, evidence_rows),
            'interpretation_note': 'Inventory presence and current status do not replace live validation, analytics, governance, or ownership evidence.',
            'interpretation_tone': _interpretation_tone(report_type, total_assets, topology_rows, evidence_rows),
            'decisions': recommendations[:4],
        },
        'detail_pages': detail_pages,
        'recommendations': {
            'metrics': _recommendation_metrics(recommendations),
            'rows': recommendations,
            'governance': [
                {'field': 'Primary Action', 'requirement': recommendations[0]['title'] if recommendations else 'Maintain committed inventory evidence.'},
                {'field': 'Validation Criteria', 'requirement': 'Confirm identity, scope, collection time, live state, accountable owner, and approved response before closure.'},
                {'field': 'Assigned Owners', 'requirement': _owner_summary(recommendations)},
                {'field': 'Change Control', 'requirement': 'No Kubernetes resource change is authorized by this inventory report alone.'},
            ],
        },
        'methodology': {
            'metrics': [
                _metric('Data Sources', '1', 'Committed Inventory', 'normal'),
                _metric('Assets', str(total_assets), profile['asset_label'], 'info'),
                _metric('Collected', collected_at, 'Latest generation', 'normal'),
                _metric('Observation Boundary', 'Snapshot', 'Committed', 'normal'),
            ],
            'sources': [
                {'source': 'Kubernetes Committed Inventory', 'freshness': 'Current Generation', 'collected': collected_at},
            ],
            'rules': [
                {'ref': 'M1', 'rule': 'Reporting Period', 'setting': period_label},
                {'ref': 'M2', 'rule': 'Data Cut-Off', 'setting': data_cutoff},
                {'ref': 'M3', 'rule': 'Inventory Basis', 'setting': 'Latest committed generation'},
                {'ref': 'M4', 'rule': 'Relationship Policy', 'setting': 'Committed fields only'},
                {'ref': 'M5', 'rule': 'Missing Evidence', 'setting': 'Explicit Not Available'},
            ],
            'included': profile['included'],
            'excluded': profile['excluded'],
            'limitations': [
                'Inventory values describe the latest committed generation and may differ from live state after the data cut-off.',
                'Missing fields remain explicit and are never converted to zero, healthy, compliant, or empty.',
                'Operational changes require live validation and approved change controls.',
            ],
            'status_language': [
                {'ref': 'S1', 'title': 'Not Available', 'description': 'No committed evidence exists for the requested dimension.'},
                {'ref': 'S2', 'title': 'Partial Coverage', 'description': 'Evidence exists for only part of the selected scope or fields.'},
                {'ref': 'S3', 'title': 'Current', 'description': 'The value belongs to the latest committed inventory generation.'},
                {'ref': 'S4', 'title': 'Source Unavailable', 'description': 'The inventory source was unreachable or did not provide data at the cut-off.'},
            ],
        },
    }



def _executive_title(report_type: str) -> str:
    titles = {
        'inventory_overview': 'Executive Inventory Brief',
        'node_inventory': 'Executive Node Brief',
        'namespace_inventory': 'Executive Namespace Brief',
        'workload_inventory': 'Executive Workload Brief',
        'pod_inventory': 'Executive Pod Brief',
        'service_inventory': 'Executive Service Brief',
        'ingress_inventory': 'Executive Ingress Brief',
        'storage_inventory': 'Executive Storage Brief',
        'topology_inventory': 'Executive Topology Brief',
    }
    return titles.get(report_type, 'Executive Inventory Brief')

def _build_detail_pages(
    report_type: str,
    profile: Mapping[str, Any],
    rows: list[dict[str, Any]],
    overview: Mapping[str, Any],
    status_rows: list[dict[str, Any]],
    type_rows: list[dict[str, Any]],
    cluster_rows: list[dict[str, Any]],
    topology_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    total_assets: int,
    collected_at: str,
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    detail_titles = profile['detail_pages']
    primary_columns = [item['label'] for item in profile['primary_fields']]
    primary_rows = _table_rows(rows, profile['primary_fields'], limit=7)

    if report_type == 'inventory_overview':
        resource_rows = [
            [sanitize_text(item.get('resource_type')), str(_int(item.get('assets'))), sanitize_text(item.get('status'))]
            for item in rows[:9]
        ]
        readiness = _float(overview.get('node_readiness_percent'))
        ready = _int(overview.get('ready_nodes'))
        not_ready = _int(overview.get('not_ready_nodes'))
        overview_metrics = [
            _metric('Clusters', str(_int(overview.get('clusters'))), 'Committed', 'normal'),
            _metric('Nodes', str(_int(overview.get('nodes'))), f'{_percent(readiness)} Ready' if readiness is not None else 'Not Available', 'normal' if not_ready == 0 else 'warning'),
            _metric('Workloads', str(_int(overview.get('workloads'))), 'Committed', 'info'),
            _metric('Pods', str(_int(overview.get('pods'))), 'Committed', 'info'),
        ]
        pages.append(_detail_page(
            detail_titles[0], overview_metrics,
            'Resource Composition', 'Committed Kubernetes asset counts.',
            ['Resource', 'Count', 'Status'], resource_rows,
            'Composition Interpretation', 'Counts describe inventory presence, not runtime health or utilization.',
            'Resource Composition Register', ['Resource', 'Count', 'Status'], resource_rows,
        ))
        node_status_rows = [['Ready', str(ready), 'Current'], ['Not Ready', str(not_ready), 'Review' if not_ready else 'Clear']]
        pages.append(_detail_page(
            detail_titles[1], [
                _metric('Total Nodes', str(_int(overview.get('nodes'))), 'Committed', 'normal'),
                _metric('Ready', str(ready), 'Healthy' if not_ready == 0 else 'Review', 'normal' if not_ready == 0 else 'warning'),
                _metric('Not Ready', str(not_ready), 'Clear' if not_ready == 0 else 'Open', 'normal' if not_ready == 0 else 'warning'),
                _metric('Readiness', _percent(readiness), 'Committed', 'normal' if not_ready == 0 else 'warning'),
            ],
            'Node Readiness Position', 'Ready and not-ready node counts.',
            ['State', 'Count', 'Assessment'], node_status_rows,
            'Readiness Boundary', 'Readiness does not establish node pressure, utilization, or maintenance state.',
            'Node Readiness Register', ['State', 'Count', 'Assessment'], node_status_rows,
        ))
        coverage_rows = [
            ['Namespaces', str(_int(overview.get('namespaces'))), 'Committed'],
            ['Workloads', str(_int(overview.get('workloads'))), 'Committed'],
            ['Pods', str(_int(overview.get('pods'))), 'Committed'],
        ]
        pages.append(_detail_page(
            detail_titles[2], [
                _metric('Namespaces', str(_int(overview.get('namespaces'))), 'Committed', 'normal'),
                _metric('Workloads', str(_int(overview.get('workloads'))), 'Committed', 'normal'),
                _metric('Pods', str(_int(overview.get('pods'))), 'Committed', 'normal'),
                _metric('Relationship Edges', str(sum(_int(item.get('edges')) for item in topology_rows)), 'Derived from committed fields', 'info'),
            ],
            'Workload and Pod Coverage', 'Committed resource totals and available relationship counts.',
            ['Resource', 'Count', 'Status'], coverage_rows,
            'Relationship Boundary', 'Aggregate counts do not create synthetic workload-to-pod or pod-to-node mappings.',
            'Relationship Register', ['Relationship', 'Scope', 'Edges', 'Status'], _topology_table_rows(topology_rows, limit=7),
        ))
        network_rows = [
            ['Services', str(_int(overview.get('services'))), 'Committed'],
            ['Ingresses', str(_int(overview.get('ingresses'))), 'Committed'],
            ['Configuration', str(_int(overview.get('configuration'))), 'Committed'],
            ['Storage', str(_int(overview.get('storage'))), 'Committed'],
        ]
        pages.append(_detail_page(
            detail_titles[3], [
                _metric('Services', str(_int(overview.get('services'))), 'Committed', 'normal'),
                _metric('Ingresses', str(_int(overview.get('ingresses'))), 'Committed', 'normal'),
                _metric('Configuration', str(_int(overview.get('configuration'))), 'Committed', 'info'),
                _metric('Storage', str(_int(overview.get('storage'))), 'Committed', 'info'),
            ],
            'Network and Storage Counts', 'Committed service, ingress, configuration, and storage totals.',
            ['Resource', 'Count', 'Status'], network_rows,
            'Network and Storage Boundary', 'Counts do not establish endpoint health, TLS validity, dependency direction, or storage capacity.',
            'Network and Storage Register', ['Resource', 'Count', 'Status'], network_rows,
        ))
    elif report_type == 'topology_inventory':
        readiness = _float(overview.get('node_readiness_percent'))
        ready = _int(overview.get('ready_nodes'))
        not_ready = _int(overview.get('not_ready_nodes'))
        cluster_rows_data = [
            ['Clusters', str(_int(overview.get('clusters'))), 'Committed'],
            ['Nodes', str(_int(overview.get('nodes'))), 'Committed'],
            ['Namespaces', str(_int(overview.get('namespaces'))), 'Committed'],
            ['Ready Nodes', str(ready), 'Current'],
        ]
        pages.append(_detail_page(
            detail_titles[0], [
                _metric('Clusters', str(_int(overview.get('clusters'))), 'Committed', 'normal'),
                _metric('Nodes', str(_int(overview.get('nodes'))), f'{_percent(readiness)} Ready' if readiness is not None else 'Not Available', 'normal' if not_ready == 0 else 'warning'),
                _metric('Namespaces', str(_int(overview.get('namespaces'))), 'Committed', 'info'),
                _metric('Ready Nodes', str(ready), 'Current', 'normal' if not_ready == 0 else 'warning'),
            ],
            'Cluster Composition', 'Committed cluster, node, namespace, and readiness counts.',
            ['Resource', 'Count', 'Status'], cluster_rows_data,
            'Cluster Topology Boundary', 'Composition counts do not create node identities, zones, or cluster-to-node edges.',
            'Cluster Topology Register', ['Resource', 'Count', 'Status'], cluster_rows_data,
        ))

        namespace_topology = _filter_topology_rows(topology_rows, ('namespace',))
        namespace_rows_data = [
            ['Namespaces', str(_int(overview.get('namespaces'))), 'Committed'],
            ['Workloads', str(_int(overview.get('workloads'))), 'Committed'],
            ['Pods', str(_int(overview.get('pods'))), 'Committed'],
            ['Services', str(_int(overview.get('services'))), 'Committed'],
            ['Ingresses', str(_int(overview.get('ingresses'))), 'Committed'],
            ['Storage', str(_int(overview.get('storage'))), 'Committed'],
        ]
        pages.append(_detail_page(
            detail_titles[1], [
                _metric('Namespaces', str(_int(overview.get('namespaces'))), 'Committed', 'normal'),
                _metric('Workloads', str(_int(overview.get('workloads'))), 'Committed', 'normal'),
                _metric('Pods', str(_int(overview.get('pods'))), 'Committed', 'info'),
                _metric('Namespace Edges', str(sum(_int(item.get('edges')) for item in namespace_topology)), 'Committed fields', 'info'),
            ],
            'Namespace Composition', 'Committed namespace, workload, pod, network, and storage totals.',
            ['Resource', 'Count', 'Status'], namespace_rows_data,
            'Namespace Relationship Boundary', 'Only committed namespace relationship fields are published; aggregate totals do not create synthetic edges.',
            'Namespace Topology Register', ['Relationship', 'Scope', 'Edges', 'Status'], _topology_table_rows(namespace_topology, limit=7),
        ))

        workload_topology = _filter_topology_rows(topology_rows, ('workload', 'pod'))
        workload_rows_data = [
            ['Workloads', str(_int(overview.get('workloads'))), 'Committed'],
            ['Pods', str(_int(overview.get('pods'))), 'Committed'],
            ['Nodes', str(_int(overview.get('nodes'))), 'Committed'],
        ]
        pages.append(_detail_page(
            detail_titles[2], [
                _metric('Workloads', str(_int(overview.get('workloads'))), 'Committed', 'normal'),
                _metric('Pods', str(_int(overview.get('pods'))), 'Committed', 'normal'),
                _metric('Nodes', str(_int(overview.get('nodes'))), 'Committed', 'info'),
                _metric('Relationship Edges', str(sum(_int(item.get('edges')) for item in workload_topology)), 'Committed fields', 'info'),
            ],
            'Workload and Pod Composition', 'Committed workload, pod, and node totals.',
            ['Resource', 'Count', 'Status'], workload_rows_data,
            'Placement Relationship Boundary', 'Workload-to-pod and pod-to-node mappings are published only from committed relationship fields.',
            'Workload and Pod Topology Register', ['Relationship', 'Scope', 'Edges', 'Status'], _topology_table_rows(workload_topology, limit=7),
        ))

        network_topology = _filter_topology_rows(topology_rows, ('service', 'ingress', 'storage', 'configuration', 'pvc', 'volume'))
        network_rows_data = [
            ['Services', str(_int(overview.get('services'))), 'Committed'],
            ['Ingresses', str(_int(overview.get('ingresses'))), 'Committed'],
            ['Configuration', str(_int(overview.get('configuration'))), 'Committed'],
            ['Storage', str(_int(overview.get('storage'))), 'Committed'],
        ]
        network_register_rows = _topology_table_rows(network_topology, limit=7)
        network_register_columns = ['Relationship', 'Scope', 'Edges', 'Status']
        if not network_register_rows:
            network_register_rows = network_rows_data
            network_register_columns = ['Resource', 'Count', 'Status']
        pages.append(_detail_page(
            detail_titles[3], [
                _metric('Services', str(_int(overview.get('services'))), 'Committed', 'normal'),
                _metric('Ingresses', str(_int(overview.get('ingresses'))), 'Committed', 'normal'),
                _metric('Configuration', str(_int(overview.get('configuration'))), 'Committed', 'info'),
                _metric('Storage', str(_int(overview.get('storage'))), 'Committed', 'info'),
            ],
            'Network and Storage Composition', 'Committed service, ingress, configuration, and storage totals.',
            ['Resource', 'Count', 'Status'], network_rows_data,
            'Network and Storage Relationship Boundary', 'Counts do not establish endpoint health, TLS validity, dependency direction, or storage capacity.',
            'Network and Storage Topology Register', network_register_columns, network_register_rows,
        ))
    else:
        pages.append(_detail_page(
            detail_titles[0], [
                _metric(profile['asset_label'], str(total_assets), 'Committed', 'normal'),
                _metric('Clusters', str(len(cluster_rows)), 'Scope', 'info'),
                _metric('Statuses', str(len(status_rows)), 'Distinct', 'info'),
                _metric('Types', str(len(type_rows)), 'Distinct', 'info'),
            ],
            'Asset Register', 'Leading committed asset records.',
            primary_columns, primary_rows,
            'Inventory Interpretation', 'Asset records describe the committed snapshot and should be validated against live state before action.',
            'Asset Evidence Register', primary_columns, primary_rows,
        ))
        status_table = [[item['label'], str(item['assets']), _status_assessment(item['label'])] for item in status_rows]
        pages.append(_detail_page(
            detail_titles[1], [
                _metric('Assets', str(total_assets), 'Committed', 'normal'),
                _metric('Distinct Statuses', str(len(status_rows)), 'Observed', 'info'),
                _metric('Largest Status Group', _largest_label(status_rows), 'Committed', 'info'),
                _metric('Review States', str(_review_status_count(status_rows)), 'Requires attention', 'warning' if _review_status_count(status_rows) else 'normal'),
            ],
            'Status Distribution', 'Committed assets grouped by current inventory status.',
            ['Status', 'Assets', 'Assessment'], status_table,
            'Lifecycle Boundary', 'Inventory status is a point-in-time field and does not establish historical stability.',
            'Lifecycle and Status Register', ['Status', 'Assets', 'Assessment'], status_table,
        ))
        pages.append(_detail_page(
            detail_titles[2], [
                _metric('Relationship Types', str(len({item['relationship'] for item in topology_rows})), 'Committed', 'info'),
                _metric('Relationship Edges', str(sum(_int(item.get('edges')) for item in topology_rows)), 'Derived', 'info'),
                _metric('Scopes', str(len({item['scope'] for item in topology_rows})), 'Observed', 'normal'),
                _metric('Coverage', 'Partial' if topology_rows else 'Not Available', 'Committed fields only', 'warning'),
            ],
            'Relationship Evidence', 'Relationships derived from committed inventory fields.',
            ['Relationship', 'Scope', 'Edges', 'Status'], _topology_table_rows(topology_rows, limit=7),
            'Relationship Boundary', 'No relationship is inferred from aggregate totals or naming similarity alone.',
            'Relationship Coverage Register', ['Relationship', 'Scope', 'Edges', 'Status'], _topology_table_rows(topology_rows, limit=7),
        ))
        evidence_table = [[item['label'], item['coverage'], item['state']] for item in evidence_rows]
        pages.append(_detail_page(
            detail_titles[3], [
                _metric('Evidence Fields', str(len(evidence_rows)), 'Profile', 'info'),
                _metric('Complete Fields', str(sum(1 for item in evidence_rows if item['state'] == 'Complete')), 'Committed', 'normal'),
                _metric('Partial Fields', str(sum(1 for item in evidence_rows if item['state'] == 'Partial Coverage')), 'Review', 'warning'),
                _metric('Unavailable Fields', str(sum(1 for item in evidence_rows if item['state'] == 'Not Available')), 'Review', 'warning'),
            ],
            'Governance Evidence Coverage', 'Leading field-level availability across the selected asset rows.',
            ['Evidence', 'Coverage', 'State'], evidence_table[:5],
            'Decision Boundary', 'Missing evidence must not be converted to compliant, healthy, internal-only, or zero risk.',
            'Governance and Risk Register', ['Evidence', 'Coverage', 'State'], evidence_table,
        ))

    publication_rows = [
        ['Committed Assets', str(total_assets), 'Ready' if total_assets else 'No Data'],
        ['Collected At', collected_at, 'Current'],
        ['Status Groups', str(len(status_rows)), 'Observed'],
        ['Type Groups', str(len(type_rows)), 'Observed'],
        ['Relationship Rows', str(len(topology_rows)), 'Partial' if topology_rows else 'Not Available'],
    ]
    pages.append(_detail_page(
        detail_titles[4], [
            _metric('Assets', str(total_assets), 'Committed', 'normal'),
            _metric('Collected', collected_at, 'Latest generation', 'normal'),
            _metric('Evidence Fields', str(len(evidence_rows)), 'Profile', 'info'),
            _metric('Publication', 'Ready' if total_assets else 'No Data', 'Fixed 9-page contract', 'normal' if total_assets else 'warning'),
        ],
        'Source Evidence', 'Committed generation, collection time, and publication coverage.',
        ['Evidence', 'Value', 'Status'], publication_rows,
        'Publication Readiness', 'Rows are published only from committed inventory evidence; absent fields remain explicit.',
        'Publication Gate Register', ['Evidence', 'Value', 'Status'], publication_rows,
    ))
    return pages


def _detail_page(
    title_data: Sequence[str],
    metrics: list[dict[str, str]],
    left_title: str,
    left_subtitle: str,
    columns: list[str],
    rows: list[list[str]],
    right_title: str,
    right_body: str,
    register_title: str,
    register_columns: list[str],
    register_rows: list[list[str]],
) -> dict[str, Any]:
    title, subtitle = title_data
    return {
        'title': title,
        'subtitle': subtitle,
        'metrics': metrics,
        'left': {
            'title': left_title,
            'subtitle': left_subtitle,
            'columns': columns,
            'rows': rows or [['Not Available', 'No committed evidence', 'Review']],
        },
        'right': {
            'title': right_title,
            'subtitle': 'Operational interpretation and evidence boundary.',
            'callout_title': right_title,
            'callout_body': right_body,
            'callout_note': 'Validate all operational actions against live Kubernetes state and approved ownership before execution.',
            'tone': 'normal',
        },
        'register': {
            'title': register_title,
            'subtitle': 'Committed evidence retained in a fixed technical register.',
            'columns': register_columns,
            'rows': register_rows or [['Not Available', 'No committed evidence', 'Review']],
        },
    }


def _executive_metrics(
    report_type: str,
    profile: Mapping[str, Any],
    rows: list[dict[str, Any]],
    overview: Mapping[str, Any],
    summary: Mapping[str, Any],
    topology_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if report_type in {'inventory_overview', 'topology_inventory'}:
        return [
            _metric('Clusters', str(_int(overview.get('clusters'))), 'Committed', 'normal'),
            _metric('Nodes', str(_int(overview.get('nodes'))), f'{_int(overview.get("ready_nodes"))} Ready', 'normal' if _int(overview.get('not_ready_nodes')) == 0 else 'warning'),
            _metric('Workloads', str(_int(overview.get('workloads'))), 'Committed', 'info'),
            _metric('Relationship Edges', str(sum(_int(item.get('edges')) for item in topology_rows)), 'Committed fields', 'info'),
        ]
    status_counter = Counter(sanitize_text(item.get('status'), fallback='Unknown') for item in rows)
    review_count = sum(count for label, count in status_counter.items() if _status_assessment(label) == 'Review')
    return [
        _metric(profile['asset_label'], str(_int(summary.get('total_assets')) or len(rows)), 'Committed', 'normal'),
        _metric('Clusters', str(_int(summary.get('cluster_scope'))), 'Scope', 'info'),
        _metric('Namespaces', str(_int(summary.get('namespace_scope'))), 'Scope', 'info'),
        _metric('Review Records', str(review_count), 'Status based', 'warning' if review_count else 'normal'),
    ]


def _evidence_rows(profile: Mapping[str, Any], rows: list[dict[str, Any]], overview: Mapping[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    fields = profile['evidence_fields']
    if overview:
        for field in fields:
            value = overview.get(field['key'])
            available = _is_available(value)
            result.append({
                'label': field['label'],
                'coverage': '1 of 1' if available else '0 of 1',
                'state': 'Complete' if available else 'Not Available',
            })
        return result
    total = len(rows)
    for field in fields:
        available = sum(1 for row in rows if _is_available(row.get(field['key'])))
        if total == 0 or available == 0:
            state = 'Not Available'
        elif available == total:
            state = 'Complete'
        else:
            state = 'Partial Coverage'
        result.append({'label': field['label'], 'coverage': f'{available} of {total}', 'state': state})
    return result


def _recommendations(
    profile: Mapping[str, Any],
    rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, str]],
    topology_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    has_gap = any(item['state'] != 'Complete' for item in evidence_rows)
    recommendations: list[dict[str, str]] = []
    for index, (title, owner) in enumerate(profile['recommendations'], start=1):
        priority = 'P2' if has_gap and index <= 2 else 'P3'
        status = 'Open' if priority == 'P2' else 'Planned'
        target = 'Next Week' if priority == 'P2' else 'This Month'
        recommendations.append({
            'ref': f'R{index}',
            'priority': priority,
            'title': title,
            'description': _recommendation_description(title),
            'owner': owner,
            'target': target,
            'status': status,
        })
    if not rows:
        recommendations.insert(0, {
            'ref': 'R0', 'priority': 'P2', 'title': 'Restore Committed Inventory Evidence',
            'description': _recommendation_description('Restore Committed Inventory Evidence'),
            'owner': 'Platform Operations', 'target': 'Next Week', 'status': 'Open',
        })
    if not topology_rows and profile['title'] == 'Kubernetes Topology':
        recommendations.insert(0, {
            'ref': 'R0', 'priority': 'P2', 'title': 'Restore Committed Topology Edges',
            'description': _recommendation_description('Restore Committed Topology Edges'),
            'owner': 'Platform Operations', 'target': 'Next Week', 'status': 'Open',
        })
    return recommendations[:5]


def _recommendation_description(title: str) -> str:
    return (
        f'Confirm committed evidence for {title.lower()}, validate live state, '
        'assign the owner, and retain closure evidence.'
    )


def _interpretation_tone(
    report_type: str,
    total_assets: int,
    topology_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, str]],
) -> str:
    if total_assets == 0:
        return 'warning'
    if report_type == 'topology_inventory' and not topology_rows:
        return 'warning'
    if any(item['state'] == 'Not Available' for item in evidence_rows):
        return 'warning'
    return 'normal'


def _filter_topology_rows(rows: list[dict[str, Any]], tokens: Sequence[str]) -> list[dict[str, Any]]:
    lowered_tokens = tuple(token.lower() for token in tokens)
    return [
        item for item in rows
        if any(token in str(item.get('relationship', '')).lower() for token in lowered_tokens)
    ]


def _recommendation_metrics(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        _metric('P1 Actions', str(sum(1 for item in rows if item['priority'] == 'P1')), 'Immediate', 'critical' if any(item['priority'] == 'P1' for item in rows) else 'normal'),
        _metric('P2 Actions', str(sum(1 for item in rows if item['priority'] == 'P2')), 'Open', 'warning'),
        _metric('P3 Actions', str(sum(1 for item in rows if item['priority'] == 'P3')), 'Planned', 'info'),
        _metric('Validation Gates', str(len(rows)), 'Required', 'info'),
    ]


def _owner_summary(rows: list[dict[str, str]]) -> str:
    counts = Counter(item['owner'] for item in rows)
    return '; '.join(f'{owner}: {count}' for owner, count in sorted(counts.items())) or 'Not Assigned'


def _interpretation_title(report_type: str, total_assets: int, topology_rows: list[dict[str, Any]]) -> str:
    if total_assets == 0:
        return 'No committed inventory assets were available.'
    if report_type == 'topology_inventory' and not topology_rows:
        return 'Resource counts are available, but committed topology edges are missing.'
    return 'Committed inventory evidence is available for the selected reporting boundary.'


def _interpretation_body(
    report_type: str,
    total_assets: int,
    distinct_statuses: int,
    distinct_types: int,
    evidence_rows: list[dict[str, str]],
) -> str:
    gaps = sum(1 for item in evidence_rows if item['state'] != 'Complete')
    if total_assets == 0:
        return 'Regenerate after the inventory synchronization worker commits a current generation for the selected scope.'
    label = 'topology composition' if report_type == 'topology_inventory' else 'inventory assets'
    return (
        f'The publication contains {total_assets} committed {label}, {distinct_statuses} status groups, '
        f'and {distinct_types} resource classifications. {gaps} evidence fields require review or remain unavailable.'
    )


def _topology_rows(payload: Mapping[str, Any], profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    filters = tuple(str(item).lower() for item in profile.get('relationship_filters', ()))
    rows: list[dict[str, Any]] = []
    for item in _sequence(payload.get('topology_edges')):
        row = _mapping(item)
        relationship = sanitize_text(row.get('relationship'), fallback='Not Available')
        if filters and not any(token in relationship.lower() for token in filters):
            continue
        rows.append({
            'relationship': relationship,
            'scope': sanitize_text(row.get('scope'), fallback='Not Available'),
            'edges': _int(row.get('edges')),
            'status': sanitize_text(row.get('status'), fallback='Committed'),
        })
    rows.sort(key=lambda item: (-item['edges'], item['relationship'], item['scope']))
    return rows


def _topology_table_rows(rows: list[dict[str, Any]], *, limit: int) -> list[list[str]]:
    return [
        [item['relationship'], item['scope'], str(item['edges']), item['status']]
        for item in rows[:limit]
    ]


def _table_rows(rows: list[dict[str, Any]], fields: Sequence[Mapping[str, str]], *, limit: int) -> list[list[str]]:
    return [
        [_display(row.get(field['key'])) for field in fields]
        for row in rows[:limit]
    ]


def _distribution_rows(value: Any, label_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _sequence(value):
        row = _mapping(item)
        rows.append({'label': sanitize_text(row.get(label_key), fallback='Unknown'), 'assets': _int(row.get('assets'))})
    rows.sort(key=lambda item: (-item['assets'], item['label']))
    return rows


def _largest_label(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return 'Not Available'
    return f"{rows[0]['label']} ({rows[0]['assets']})"


def _review_status_count(rows: list[dict[str, Any]]) -> int:
    return sum(item['assets'] for item in rows if _status_assessment(item['label']) == 'Review')


def _status_assessment(value: Any) -> str:
    text = sanitize_text(value, fallback='Unknown').lower()
    if any(token in text for token in ('not ready', 'failed', 'pending', 'terminating', 'disabled', 'unknown')):
        return 'Review'
    return 'Current'


def _metric(label: str, value: str, note: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'note': note, 'tone': tone}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent(value: float | None) -> str:
    if value is None:
        return 'Not Available'
    return f'{value:.1f}%'


def _is_available(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return sanitize_text(value, fallback='').strip().lower() not in _UNAVAILABLE


def _display(value: Any, *, fallback: str = 'Not Available') -> str:
    if isinstance(value, datetime):
        return value.strftime('%d %b %Y %H:%M UTC')
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, float):
        return f'{value:.2f}'.rstrip('0').rstrip('.')
    if isinstance(value, (dict, list, tuple, set)):
        return sanitize_text(', '.join(str(item) for item in value), fallback=fallback)
    return sanitize_text(value, fallback=fallback)
