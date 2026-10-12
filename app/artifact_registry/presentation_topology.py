"""Bounded, read-only Artifact Registry to Kubernetes dependency graph (#1692).

This is a projection of committed RegistryWorkloadBinding rows, never a new
relationship authority or a live provider query.
"""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any

from flask import url_for

from app.artifact_registry.correlation import runtime_correlation_evidence_readiness
from app.artifact_registry.presentation_common import _providers
from app.artifact_registry.presentation_runtime import (
    _runtime_filtered_query,
    _runtime_match_state,
    _runtime_security_index,
    _runtime_security_state,
    _runtime_usage_request,
)
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.registry import RegistryWorkloadBinding

# SQL LIMIT applies before ORM hydration; graph and list represent the same slice.
_MAX_VISIBLE_BINDINGS = 45


def _node_id(kind: str, *identity: object) -> str:
    key = repr((kind, *identity)).encode('utf-8')
    return f'{kind}:{sha256(key).hexdigest()[:20]}'


def _utc_text(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def build_dependency_topology(
    *,
    source_id: int | None = None,
    cluster_id: str = '',
    namespace: str = '',
    match_type: str = '',
    exposure: str = '',
    artifact_id: int | None = None,
    search: str = '',
) -> dict[str, Any]:
    """Return a deterministic, scoped slice with exact SQL omitted-row evidence."""
    sources = _providers()
    source_ids = [int(source.id) for source in sources]
    security_index, critical_ids, high_ids, scanned_ids = _runtime_security_index(
        source_ids=source_ids,
    )
    filters = _runtime_usage_request(
        {
            'source_id': source_id,
            'cluster_id': cluster_id,
            'namespace': namespace,
            'match_type': match_type,
            'exposure': exposure,
            'artifact_id': artifact_id,
            'search': search,
        }
    )
    query, normalized_filters = _runtime_filtered_query(
        filters,
        sources=sources,
        critical_ids=critical_ids,
        high_ids=high_ids,
        scanned_ids=scanned_ids,
    )
    # Count query is independent of the graph window; no unbounded .all().
    total = query.order_by(None).count()
    bindings = (
        query.order_by(
            RegistryWorkloadBinding.artifact_id.asc(),
            RegistryWorkloadBinding.cluster_id.asc(),
            RegistryWorkloadBinding.namespace.asc(),
            RegistryWorkloadBinding.workload_name.asc(),
            RegistryWorkloadBinding.pod_name.asc(),
            RegistryWorkloadBinding.id.asc(),
        )
        .limit(_MAX_VISIBLE_BINDINGS)
        .all()
    )
    clusters = {
        str(cluster.id): cluster.name
        for cluster in Cluster.query.filter(
            Cluster.id.in_({binding.cluster_id for binding in bindings})
        ).all()
    } if bindings else {}
    source_names = {int(source.id): source.name for source in sources}

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    visible_bindings: list[dict[str, Any]] = []
    artifact_ids: set[int] = set()
    workload_keys: set[tuple[str, ...]] = set()
    pod_keys: set[tuple[str, ...]] = set()
    confidence_by_edge: dict[str, set[str]] = defaultdict(set)

    def add_node(
        kind: str,
        identity: tuple[object, ...],
        label: str,
        **data: Any,
    ) -> str:
        node_id = _node_id(kind, *identity)
        if node_id not in nodes:
            nodes[node_id] = {
                'data': {'id': node_id, 'type': kind, 'label': label, **data}
            }
        return node_id

    def add_edge(source: str, target: str, kind: str) -> str:
        edge_id = _node_id('edge', source, target, kind)
        if edge_id not in edges:
            edges[edge_id] = {
                'data': {
                    'id': edge_id,
                    'source': source,
                    'target': target,
                    'relationship': kind,
                    'confidence': 'context',
                }
            }
        return edge_id

    for binding in bindings:
        artifact = binding.artifact
        repository = artifact.repository
        project = repository.project
        artifact_pk = int(artifact.id)
        artifact_ids.add(artifact_pk)
        security = security_index.get(artifact_pk) or _runtime_security_state(
            artifact.scan_status, artifact.vulnerability_summary
        )
        registry_name = source_names.get(int(project.integration_instance_id), 'Registry')
        artifact_label = f'{project.name}/{repository.name}'
        artifact_node = add_node(
            'artifact', (artifact_pk,), artifact_label,
            subtitle=artifact.digest[:25] + '…' if len(artifact.digest) > 25 else artifact.digest,
            digest=artifact.digest,
            source=registry_name,
            source_id=int(project.integration_instance_id),
            scan_status=artifact.scan_status or 'Not Scanned',
            critical=security['critical'],
            high=security['high'],
            security=security['label'],
            url=url_for('artifact_registry.runtime', artifact_id=artifact_pk),
        )
        cluster_key = str(binding.cluster_id)
        cluster_label = clusters.get(cluster_key, cluster_key)
        branch_key = (artifact_pk, cluster_key)
        cluster_node = add_node(
            'cluster', branch_key, cluster_label,
            subtitle='Kubernetes Cluster',
            cluster_id=cluster_key,
        )
        namespace_key = (artifact_pk, cluster_key, binding.namespace)
        namespace_node = add_node(
            'namespace', namespace_key, binding.namespace,
            subtitle='Namespace',
        )
        workload_type = binding.workload_type or 'Workload'
        workload_name = binding.workload_name or 'Not Resolved'
        workload_key = (
            str(artifact_pk), cluster_key, binding.namespace,
            workload_type, workload_name,
        )
        workload_node = None
        if binding.workload_name:
            workload_keys.add(workload_key)
            workload_node = add_node(
                'workload', workload_key, workload_name,
                subtitle=workload_type,
            )
        pod_key = (
            str(artifact_pk), cluster_key, binding.namespace,
            'pod', binding.pod_name,
        )
        pod_keys.add(pod_key)
        pod_node = add_node(
            'pod', pod_key, binding.pod_name,
            subtitle='Pod',
        )
        usage_details = binding.details if isinstance(binding.details, dict) else {}
        usages = usage_details.get('containers')
        containers = [
            {
                'name': str(usage.get('name') or 'Container'),
                'kind': str(usage.get('source_kind') or 'container'),
            }
            for usage in (usages if isinstance(usages, list) else [])
            if isinstance(usage, dict)
        ] or [{'name': binding.container_name or 'Container', 'kind': 'container'}]
        confidence = 'strong' if binding.match_type == 'digest' else 'medium'
        match = _runtime_match_state(binding.match_type, binding.confidence)
        relationships = [
            (artifact_node, cluster_node, 'runtime_usage'),
            (cluster_node, namespace_node, 'contains'),
        ]
        if workload_node is not None:
            relationships.extend([
                (namespace_node, workload_node, 'contains'),
                (workload_node, pod_node, 'owns'),
            ])
        else:
            relationships.append((namespace_node, pod_node, 'contains'))
        for source, target, relationship in relationships:
            edge_key = add_edge(source, target, relationship)
            if relationship == 'runtime_usage':
                confidence_by_edge[edge_key].add(confidence)
        visible_bindings.append({
            'id': int(binding.id),
            'artifact_id': artifact_pk,
            'artifact': artifact_label,
            'digest': artifact.digest,
            'source': registry_name,
            'cluster': cluster_label,
            'cluster_id': cluster_key,
            'namespace': binding.namespace,
            'workload': f'{workload_type}/{workload_name}',
            'pod': binding.pod_name,
            'containers': containers,
            'match': match['label'],
            'match_type': binding.match_type,
            'confidence': match['confidence'],
            'security': security['label'],
            'critical': security['critical'],
            'high': security['high'],
            'image_reference': binding.image_reference,
            'observed_at': _utc_text(binding.observed_at),
            'registry_observed_at': usage_details.get('registry_observed_at'),
            'pod_collected_at': usage_details.get('pod_collected_at'),
            'node_id': pod_node,
            'artifact_node_id': artifact_node,
            'url': url_for('artifact_registry.runtime', artifact_id=artifact_pk),
        })

    for edge_id, confidences in confidence_by_edge.items():
        edges[edge_id]['data']['confidence'] = (
            next(iter(confidences)) if len(confidences) == 1 else 'mixed'
        )

    readiness = runtime_correlation_evidence_readiness(db.session)
    return {
        'nodes': list(nodes.values()),
        'edges': list(edges.values()),
        'bindings': visible_bindings,
        'summary': {
            'total_bindings': total,
            'displayed_bindings': len(visible_bindings),
            'omitted_bindings': max(total - len(visible_bindings), 0),
            'truncated': total > len(visible_bindings),
            'artifacts_visible': len(artifact_ids),
            'workloads_visible': len(workload_keys),
            'pods_visible': len(pod_keys),
            'max_visible_bindings': _MAX_VISIBLE_BINDINGS,
        },
        'evidence': readiness,
        'filters': {
            'source_id': source_id,
            'cluster_id': normalized_filters['cluster'],
            'namespace': normalized_filters['namespace'],
            'match_type': normalized_filters['match'],
            'exposure': normalized_filters['exposure'],
            'artifact_id': artifact_id,
            'q': search,
        },
    }
