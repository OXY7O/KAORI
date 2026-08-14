from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.kubernetes.resources.common import format_age
from app.inventory.kubernetes.resources.configuration_semantics import (
    COLLECTED,
    CONFIGMAP_EVIDENCE_KEY,
    POD_EVIDENCE_KEY,
    SECRET_EVIDENCE_KEY,
    aggregate_collection_states,
    collection_state,
    configuration_evidence_key,
    mutation_presentation,
    pod_reference_presentation,
    secret_type_presentation,
)
from app.inventory.kubernetes.resources.pod_semantics import pod_operational_state
from app.models import Cluster, ClusterInventory, ConfigurationInventory, PodInventory

KEY_PREVIEW_LIMIT = 100
RELATED_POD_PREVIEW_LIMIT = 8


def _configuration_query():
    query = db.session.query(
        ConfigurationInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == ConfigurationInventory.cluster_id)
    return filter_current_generation(query, ConfigurationInventory)


def _apply_filters(
    query,
    *,
    cluster_id: str | None,
    namespace: str | None,
    object_type: str | None,
    search: str | None,
):
    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(ConfigurationInventory.namespace == namespace)
    if object_type:
        query = query.filter(ConfigurationInventory.object_type == object_type)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                ConfigurationInventory.name.ilike(pattern),
                ConfigurationInventory.namespace.ilike(pattern),
                ConfigurationInventory.object_type.ilike(pattern),
                ConfigurationInventory.secret_type.ilike(pattern),
            )
        )
    return query


def _scope_evidence(cluster_id: str | None) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    query = ClusterInventory.query
    if cluster_id:
        query = query.filter(ClusterInventory.cluster_id == cluster_id)
    rows = query.with_entities(ClusterInventory.cluster_id, ClusterInventory.collection_evidence).all()
    evidence_by_cluster = {str(row_cluster_id): dict(evidence or {}) for row_cluster_id, evidence in rows}
    return evidence_by_cluster, list(evidence_by_cluster.values())


def _reference_counts(
    configuration_rows: list[tuple[int, str, str, str, str]],
    evidence_by_cluster: dict[str, dict[str, Any]],
) -> dict[int, int]:
    if not configuration_rows:
        return {}

    eligible_cluster_ids = {
        cluster_id
        for _, cluster_id, _, _, _ in configuration_rows
        if collection_state(evidence_by_cluster.get(cluster_id), POD_EVIDENCE_KEY) == COLLECTED
    }
    if not eligible_cluster_ids:
        return {}

    lookup = {
        (cluster_id, namespace, object_type, name): item_id
        for item_id, cluster_id, namespace, object_type, name in configuration_rows
        if cluster_id in eligible_cluster_ids
    }
    namespaces = sorted(
        {namespace for _, cluster_id, namespace, _, _ in configuration_rows if cluster_id in eligible_cluster_ids}
    )
    pod_query = filter_current_generation(PodInventory.query, PodInventory).filter(
        PodInventory.cluster_id.in_(sorted(eligible_cluster_ids)),
        PodInventory.namespace.in_(namespaces),
    )

    counts: dict[int, int] = defaultdict(int)
    for pod in pod_query.with_entities(
        PodInventory.cluster_id,
        PodInventory.namespace,
        PodInventory.configuration_references,
    ).yield_per(250):
        matched_item_ids: set[int] = set()
        for reference in pod.configuration_references or []:
            key = (
                str(pod.cluster_id),
                str(pod.namespace),
                str(reference.get('type') or ''),
                str(reference.get('name') or ''),
            )
            item_id = lookup.get(key)
            if item_id is not None:
                matched_item_ids.add(item_id)
        for item_id in matched_item_ids:
            counts[item_id] += 1
    return dict(counts)


def get_configuration_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = filter_current_generation(
        db.session.query(ConfigurationInventory.namespace),
        ConfigurationInventory,
    )
    if cluster_id:
        query = query.filter(ConfigurationInventory.cluster_id == cluster_id)
    return [
        namespace for (namespace,) in query.distinct().order_by(ConfigurationInventory.namespace).all() if namespace
    ]


def get_configuration_inventory_view(
    cluster_id: str | None = None,
    namespace: str | None = None,
    object_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    query = _apply_filters(
        _configuration_query(),
        cluster_id=cluster_id,
        namespace=namespace,
        object_type=object_type,
        search=search,
    )
    summary_rows = query.with_entities(
        ConfigurationInventory.id,
        ConfigurationInventory.cluster_id,
        ConfigurationInventory.namespace,
        ConfigurationInventory.object_type,
        ConfigurationInventory.name,
        ConfigurationInventory.immutable,
        ConfigurationInventory.key_names,
    ).all()
    evidence_by_cluster, scope_evidence = _scope_evidence(cluster_id)
    reference_rows = [
        (int(row.id), str(row.cluster_id), str(row.namespace), str(row.object_type), str(row.name))
        for row in summary_rows
    ]
    reference_counts = _reference_counts(reference_rows, evidence_by_cluster)

    rows, pagination = paginate_query(
        query.order_by(
            Cluster.name,
            ConfigurationInventory.namespace,
            ConfigurationInventory.object_type,
            ConfigurationInventory.name,
        ),
        page=page,
        per_page=per_page,
    )

    config_maps = secrets = immutable_items = keyless_items = total_key_names = 0
    current_reference_items = reference_not_reported_items = 0
    for row in summary_rows:
        if row.object_type == 'ConfigMap':
            config_maps += 1
        elif row.object_type == 'Secret':
            secrets += 1
        if bool(row.immutable):
            immutable_items += 1
        key_count = len(row.key_names or [])
        total_key_names += key_count
        if key_count == 0:
            keyless_items += 1

        pod_state = collection_state(evidence_by_cluster.get(str(row.cluster_id)), POD_EVIDENCE_KEY)
        if pod_state != COLLECTED:
            reference_not_reported_items += 1
        elif reference_counts.get(int(row.id), 0) > 0:
            current_reference_items += 1
        # A collected Pod snapshot with no match remains a factual zero at row/detail level.

    items: list[dict[str, Any]] = []
    for item, cluster_name, cluster_environment in rows:
        key_count = len(item.key_names or [])
        object_collection_state = collection_state(
            evidence_by_cluster.get(str(item.cluster_id)),
            configuration_evidence_key(item.object_type),
        )
        pod_collection_state = collection_state(
            evidence_by_cluster.get(str(item.cluster_id)),
            POD_EVIDENCE_KEY,
        )
        reference_count = int(reference_counts.get(item.id, 0)) if pod_collection_state == COLLECTED else None
        reference = pod_reference_presentation(reference_count, pod_collection_state)
        mutation_label, mutation_tone = mutation_presentation(bool(item.immutable))
        items.append(
            {
                'id': item.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': item.namespace,
                'name': item.name,
                'type': item.object_type,
                'type_supporting': (
                    secret_type_presentation(item.object_type, item.secret_type)
                    if item.object_type == 'Secret'
                    else 'Configuration key names only'
                ),
                'key_count': key_count,
                'immutable': bool(item.immutable),
                'mutation_label': mutation_label,
                'mutation_tone': mutation_tone,
                'identity_supporting': 'Committed key-index metadata',
                'reference_count': reference_count,
                'reference_label': reference['label'],
                'reference_supporting': reference['supporting'],
                'reference_tone': reference['tone'],
                'collection_state': object_collection_state,
                'pod_collection_state': pod_collection_state,
            }
        )

    configmap_states = [collection_state(row, CONFIGMAP_EVIDENCE_KEY) for row in scope_evidence]
    secret_states = [collection_state(row, SECRET_EVIDENCE_KEY) for row in scope_evidence]
    pod_states = [collection_state(row, POD_EVIDENCE_KEY) for row in scope_evidence]
    return {
        'total_items': pagination['total_items'],
        'config_maps': config_maps,
        'secrets': secrets,
        'immutable_items': immutable_items,
        'keyless_items': keyless_items,
        'total_key_names': total_key_names,
        'current_reference_items': current_reference_items,
        'reference_not_reported_items': reference_not_reported_items,
        'namespace_count': len({str(row.namespace) for row in summary_rows}),
        'configmap_collection_state': aggregate_collection_states(configmap_states),
        'secret_collection_state': aggregate_collection_states(secret_states),
        'pod_collection_state': aggregate_collection_states(pod_states),
        'items': items,
        'pagination': pagination,
    }


def _configuration_detail_query(configuration_id: int):
    query = db.session.query(
        ConfigurationInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == ConfigurationInventory.cluster_id)
    query = filter_current_generation(query, ConfigurationInventory)
    return query.filter(ConfigurationInventory.id == configuration_id).first()


def _related_pods(item: ConfigurationInventory, pod_collection_state: str) -> tuple[list[dict[str, Any]], int | None]:
    if pod_collection_state != COLLECTED:
        return [], None

    pod_query = filter_current_generation(PodInventory.query, PodInventory).filter_by(
        cluster_id=item.cluster_id,
        namespace=item.namespace,
    )
    related: list[dict[str, Any]] = []
    total = 0
    for pod in pod_query.order_by(PodInventory.pod_name).yield_per(100):
        references = pod.configuration_references or []
        if not any(
            reference.get('type') == item.object_type and reference.get('name') == item.name for reference in references
        ):
            continue
        total += 1
        if len(related) >= RELATED_POD_PREVIEW_LIMIT:
            continue
        state, tone, evidence = pod_operational_state(pod.phase, pod.ready)
        related.append(
            {
                'name': pod.pod_name,
                'supporting_primary': f'{pod.workload_type or "Standalone"} · {pod.workload_name or "No Owner"}',
                'supporting_secondary': evidence,
                'status': state,
                'status_tone': tone,
            }
        )
    return related, total


def _operational_context(
    *,
    object_type: str,
    object_collection_state: str,
    pod_collection_state: str,
    used_by_count: int | None,
    key_count: int,
) -> dict[str, str]:
    if object_collection_state != COLLECTED:
        return {
            'title': 'Review Collection Capability',
            'description': (
                f'{object_type} collection is recorded as {object_collection_state}. '
                'Confirm Kubernetes API availability and RBAC before relying on completeness.'
            ),
            'tone': 'warning',
            'icon': 'shield-alert',
        }
    if pod_collection_state != COLLECTED:
        return {
            'title': 'Refresh Pod Reference Evidence',
            'description': (
                f'Pod collection is recorded as {pod_collection_state}. Current Pod usage cannot be established '
                'until Pod inventory evidence is available.'
            ),
            'tone': 'warning',
            'icon': 'refresh-cw',
        }
    if used_by_count == 0:
        return {
            'title': 'No Current Pod References',
            'description': (
                'No Pod reference is represented in the current committed snapshot. Other consumers or future '
                'workload templates may still reference this object.'
            ),
            'tone': 'info',
            'icon': 'unlink',
        }
    if key_count == 0:
        return {
            'title': 'Review Keyless Configuration Object',
            'description': (
                'The object is present but no key names are represented. Confirm that an empty object is intentional.'
            ),
            'tone': 'info',
            'icon': 'key-square',
        }
    return {
        'title': 'Configuration Snapshot Ready for Review',
        'description': (
            'Key-index metadata and current Pod references are available from the latest committed inventory snapshot.'
        ),
        'tone': 'normal',
        'icon': 'circle-check',
    }


def get_configuration_detail(configuration_id: int) -> dict[str, Any] | None:
    result = _configuration_detail_query(configuration_id)
    if result is None:
        return None

    item, cluster_name = result
    cluster_inventory = ClusterInventory.query.filter_by(cluster_id=item.cluster_id).first()
    evidence = dict(cluster_inventory.collection_evidence or {}) if cluster_inventory else {}
    object_collection_state = collection_state(evidence, configuration_evidence_key(item.object_type))
    pod_collection_state = collection_state(evidence, POD_EVIDENCE_KEY)
    used_by, used_by_count = _related_pods(item, pod_collection_state)

    key_names = sorted(str(key) for key in (item.key_names or []))
    key_count = len(key_names)
    preview_names = key_names[:KEY_PREVIEW_LIMIT]
    mutation_label, mutation_tone = mutation_presentation(bool(item.immutable))
    reference = pod_reference_presentation(used_by_count, pod_collection_state)
    return {
        'id': item.id,
        'cluster_id': item.cluster_id,
        'cluster_name': cluster_name,
        'namespace': item.namespace,
        'name': item.name,
        'type': item.object_type,
        'secret_type': secret_type_presentation(item.object_type, item.secret_type),
        'key_names': key_names,
        'key_entries': [(key, 'Key name indexed') for key in preview_names],
        'key_count': key_count,
        'key_entries_truncated': key_count > KEY_PREVIEW_LIMIT,
        'immutable': bool(item.immutable),
        'mutation_label': mutation_label,
        'mutation_tone': mutation_tone,
        'age': format_age(item.created_at),
        'created_at': item.created_at,
        'collected_at': item.collected_at,
        'used_by_count': used_by_count,
        'used_by_display': reference['label'],
        'used_by': used_by,
        'used_by_truncated': used_by_count is not None and used_by_count > RELATED_POD_PREVIEW_LIMIT,
        'collection_state': object_collection_state,
        'pod_collection_state': pod_collection_state,
        'pod_reference_reported': pod_collection_state == COLLECTED,
        'operational_context': _operational_context(
            object_type=item.object_type,
            object_collection_state=object_collection_state,
            pod_collection_state=pod_collection_state,
            used_by_count=used_by_count,
            key_count=key_count,
        ),
    }
