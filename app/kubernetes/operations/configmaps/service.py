from __future__ import annotations

import base64
from typing import Any, cast

from kubernetes import client
from kubernetes.client import V1ConfigMap, V1ConfigMapList, V1NamespaceList
from kubernetes.client.exceptions import ApiException

from app.common.inventory_generation import filter_current_generation
from app.kubernetes.inventory.resources.configuration_semantics import COLLECTED, POD_EVIDENCE_KEY, collection_state
from app.kubernetes.inventory.resources.pod_semantics import pod_operational_state
from app.kubernetes.operations.configmaps.contracts import (
    ConfigMapImpactContext,
    ConfigMapTarget,
    LiveConfigMapOption,
)
from app.kubernetes.operations.configmaps.runtime import (
    authorization_call,
    live_call,
    safe_api_error,
)
from app.kubernetes.operations.configmaps.validation import (
    diff_entries,
    merge_entries,
    normalize_update_mode,
    parse_entries,
    validate_name,
    validate_namespace_name,
)
from app.models import Cluster, ClusterInventory, ConfigurationInventory, PodInventory


def _cluster(cluster_id: str) -> Cluster:
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        raise ValueError('The selected Kubernetes cluster is no longer available.')
    return cluster


def get_clusters() -> list[Cluster]:
    return Cluster.query.order_by(Cluster.name.asc()).all()


def get_context() -> dict[str, Any]:
    clusters = get_clusters()
    query = filter_current_generation(ConfigurationInventory.query, ConfigurationInventory).filter_by(
        object_type='ConfigMap'
    )
    total = query.count()
    namespace_count = query.with_entities(ConfigurationInventory.namespace).distinct().count()
    immutable_count = query.filter(ConfigurationInventory.immutable.is_(True)).count()
    return {
        'clusters': clusters,
        'total_configmaps': total,
        'namespace_count': namespace_count,
        'immutable_count': immutable_count,
    }


def get_namespaces(cluster_id: str) -> list[str]:
    if not cluster_id:
        return []
    cluster = _cluster(cluster_id)
    try:
        response = cast(
            V1NamespaceList,
            live_call(
                cluster,
                'namespace lookup',
                lambda api: api.list_namespace(_request_timeout=10),
            ),
        )
    except ApiException as exc:
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied the live namespace lookup. Verify namespace list RBAC for this cluster.'
            ) from exc
        if exc.status == 401:
            raise ValueError('Kubernetes authentication failed while loading live namespaces.') from exc
        raise ValueError('KAORI could not load live namespaces from the selected Kubernetes cluster.') from exc

    names = {str(getattr(getattr(item, 'metadata', None), 'name', '') or '').strip() for item in response.items or []}
    return sorted(name for name in names if name)


def get_configmaps(cluster_id: str, namespace: str) -> list[LiveConfigMapOption]:
    if not cluster_id or not namespace:
        return []
    cluster = _cluster(cluster_id)
    normalized_namespace = validate_namespace_name(namespace)
    try:
        response = cast(
            V1ConfigMapList,
            live_call(
                cluster,
                'list operation',
                lambda api: api.list_namespaced_config_map(
                    namespace=normalized_namespace,
                    _request_timeout=10,
                ),
            ),
        )
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError('The selected namespace no longer exists in Kubernetes.') from exc
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied the live ConfigMap lookup. Verify ConfigMap list RBAC for this namespace.'
            ) from exc
        if exc.status == 401:
            raise ValueError('Kubernetes authentication failed while loading live ConfigMaps.') from exc
        raise ValueError('KAORI could not load live ConfigMaps from the selected Kubernetes namespace.') from exc

    options: list[LiveConfigMapOption] = []
    for item in response.items or []:
        name = str(getattr(getattr(item, 'metadata', None), 'name', '') or '').strip()
        if not name:
            continue
        options.append(LiveConfigMapOption(name=name, immutable=bool(getattr(item, 'immutable', False))))
    return sorted(options, key=lambda item: item.name)


def get_target(cluster_id: str, namespace: str, configmap_name: str) -> ConfigMapTarget:
    return ConfigMapTarget(
        cluster=_cluster((cluster_id or '').strip()),
        namespace=validate_namespace_name(namespace),
        name=validate_name(configmap_name, 'ConfigMap name'),
    )


def _bound_target(form: Any) -> ConfigMapTarget:
    selected = (
        (form.get('cluster_id') or '').strip(),
        (form.get('namespace') or '').strip(),
        (form.get('configmap_name') or '').strip(),
    )
    bound = (
        (form.get('target_cluster_id') or '').strip(),
        (form.get('target_namespace') or '').strip(),
        (form.get('target_configmap_name') or '').strip(),
    )
    if not all(bound):
        raise ValueError('Reload the selected ConfigMap before submitting this operation.')
    if selected != bound:
        raise ValueError('The ConfigMap selection changed after the editor was loaded. Reload the target and retry.')
    return get_target(*bound)


def _validate_namespace(value: str, cluster_id: str) -> str:
    namespace = validate_namespace_name(value)
    cluster = _cluster(cluster_id)
    try:
        live_call(
            cluster,
            'namespace verification',
            lambda api: api.read_namespace(name=namespace, _request_timeout=10),
        )
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError('The selected namespace no longer exists in the Kubernetes cluster.') from exc
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied namespace verification. Verify namespace read RBAC for this cluster.'
            ) from exc
        if exc.status == 401:
            raise ValueError('Kubernetes authentication failed while verifying the namespace.') from exc
        raise ValueError('KAORI could not verify the selected namespace against the live Kubernetes cluster.') from exc
    return namespace


def create_configmap(form: Any, *, dry_run: bool) -> dict[str, Any]:
    cluster_id = (form.get('cluster_id') or '').strip()
    cluster = _cluster(cluster_id)
    namespace = _validate_namespace(form.get('namespace') or '', cluster_id)
    name = validate_name(form.get('configmap_name') or '', 'ConfigMap name')
    entries = parse_entries(form)
    body = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=name, namespace=namespace),
        data=entries.data or None,
        binary_data=entries.binary_data or None,
        immutable=form.get('immutable') == 'true',
    )

    def perform(*, server_dry_run: bool) -> V1ConfigMap:
        return cast(
            V1ConfigMap,
            live_call(
                cluster,
                'create operation',
                lambda api: api.create_namespaced_config_map(
                    namespace=namespace,
                    body=body,
                    dry_run='All' if server_dry_run else None,
                    _request_timeout=10,
                ),
            ),
        )

    try:
        result = perform(server_dry_run=True)
        if not dry_run:
            result = perform(server_dry_run=False)
    except ApiException as exc:
        raise safe_api_error(exc, 'create operation') from exc

    return {
        'cluster_id': cluster.id,
        'cluster_name': cluster.name,
        'namespace': namespace,
        'configmap_name': name,
        'key_names': entries.key_names,
        'key_count': len(entries.key_names),
        'payload_size_bytes': entries.payload_size_bytes,
        'immutable': bool(body.immutable),
        'resource_version': getattr(getattr(result, 'metadata', None), 'resource_version', None),
        'operation': 'validation' if dry_run else 'creation',
        'live_target_source': True,
        'inventory_target_gate': False,
    }


def read_configmap(target: ConfigMapTarget) -> dict[str, Any]:
    try:
        obj = cast(
            V1ConfigMap,
            live_call(
                target.cluster,
                'read operation',
                lambda api: api.read_namespaced_config_map(
                    name=target.name,
                    namespace=target.namespace,
                    _request_timeout=10,
                ),
            ),
        )
    except ApiException as exc:
        raise safe_api_error(exc, 'read operation') from exc

    data = dict(sorted((obj.data or {}).items()))
    binary_data: dict[str, str] = {}
    for key, value in sorted((obj.binary_data or {}).items()):
        binary_data[key] = base64.b64encode(value).decode('ascii') if isinstance(value, bytes) else str(value)
    return {
        'data': data,
        'binary_data': binary_data,
        'immutable': bool(obj.immutable),
        'resource_version': getattr(obj.metadata, 'resource_version', None),
    }


def get_impact_context(target: ConfigMapTarget) -> ConfigMapImpactContext:
    cluster_inventory = ClusterInventory.query.filter_by(cluster_id=target.cluster.id).first()
    evidence = dict(cluster_inventory.collection_evidence or {}) if cluster_inventory else {}
    pod_collection_state = collection_state(evidence, POD_EVIDENCE_KEY)
    if pod_collection_state != COLLECTED:
        return ConfigMapImpactContext(
            items=[],
            collection_state=pod_collection_state,
            reported=False,
        )

    pods = filter_current_generation(PodInventory.query, PodInventory).filter_by(
        cluster_id=target.cluster.id,
        namespace=target.namespace,
    )
    impacts: dict[tuple[str, str], dict[str, Any]] = {}
    for pod in pods.yield_per(250):
        references = pod.configuration_references or []
        if not any(
            str(reference.get('type') or '') == 'ConfigMap' and str(reference.get('name') or '') == target.name
            for reference in references
        ):
            continue
        kind = str(pod.workload_type or 'Pod')
        name = str(pod.workload_name or pod.pod_name)
        state, tone, evidence_label = pod_operational_state(pod.phase, pod.ready)
        impacts[(kind, name)] = {
            'kind': kind,
            'name': name,
            'supporting_primary': f'{kind} workload',
            'supporting_secondary': evidence_label,
            'status': state,
            'status_tone': tone,
        }
    return ConfigMapImpactContext(
        items=sorted(impacts.values(), key=lambda item: (item['kind'], item['name'])),
        collection_state=pod_collection_state,
        reported=True,
    )


def update_configmap(form: Any, *, dry_run: bool) -> dict[str, Any]:
    target = _bound_target(form)
    existing = read_configmap(target)
    if existing['immutable']:
        raise ValueError('This ConfigMap is immutable and cannot be updated. Create a new ConfigMap instead.')

    mode = normalize_update_mode(form.get('update_mode'))
    submitted = parse_entries(form)
    proposed = merge_entries(existing, submitted, mode)
    diff = diff_entries(existing, proposed)
    if not diff['added'] and not diff['changed'] and not diff['removed']:
        raise ValueError('No ConfigMap changes were detected.')
    if mode == 'replace' and form.get('confirm_replace') != 'yes':
        raise ValueError('Confirm full replacement before applying this update mode.')

    data_patch: dict[str, Any] = {}
    binary_patch: dict[str, Any] = {}
    for key in diff['added'] + diff['changed']:
        if key in proposed.data:
            data_patch[key] = proposed.data[key]
            if key in existing['binary_data']:
                binary_patch[key] = None
        else:
            binary_patch[key] = proposed.binary_data[key]
            if key in existing['data']:
                data_patch[key] = None
    if mode == 'replace':
        for key in diff['removed']:
            if key in existing['data']:
                data_patch[key] = None
            if key in existing['binary_data']:
                binary_patch[key] = None

    body: dict[str, Any] = {'metadata': {'resourceVersion': existing['resource_version']}}
    if data_patch:
        body['data'] = data_patch
    if binary_patch:
        body['binaryData'] = binary_patch

    def perform(*, server_dry_run: bool) -> V1ConfigMap:
        return cast(
            V1ConfigMap,
            live_call(
                target.cluster,
                'update operation',
                lambda api: api.patch_namespaced_config_map(
                    name=target.name,
                    namespace=target.namespace,
                    body=body,
                    dry_run='All' if server_dry_run else None,
                    _request_timeout=10,
                ),
            ),
        )

    try:
        result = perform(server_dry_run=True)
        if not dry_run:
            result = perform(server_dry_run=False)
    except ApiException as exc:
        raise safe_api_error(exc, 'update operation') from exc

    impact = get_impact_context(target)
    return {
        'cluster_id': target.cluster.id,
        'cluster_name': target.cluster.name,
        'namespace': target.namespace,
        'configmap_name': target.name,
        'mode': mode,
        'diff': diff,
        'key_count': len(proposed.key_names),
        'payload_size_bytes': proposed.payload_size_bytes,
        'resource_version': getattr(getattr(result, 'metadata', None), 'resource_version', None),
        'impact_count': impact.count,
        'impact_collection_state': impact.collection_state,
        'operation': 'validation' if dry_run else 'update',
        'live_target_source': True,
        'inventory_target_gate': False,
        'impact_context_source': 'latest_committed_pod_inventory',
    }


def _validate_delete_authorization(target: ConfigMapTarget) -> None:
    review = client.V1SelfSubjectAccessReview(
        spec=client.V1SelfSubjectAccessReviewSpec(
            resource_attributes=client.V1ResourceAttributes(
                group='',
                resource='configmaps',
                verb='delete',
                namespace=target.namespace,
                name=target.name,
            )
        )
    )
    try:
        response = authorization_call(
            target.cluster,
            'delete authorization preflight',
            lambda api: api.create_self_subject_access_review(
                body=review,
                _request_timeout=10,
            ),
        )
    except ApiException as exc:
        if exc.status == 401:
            raise ValueError('Kubernetes authentication failed while validating ConfigMap delete access.') from exc
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied the delete authorization preflight. '
                'Verify SelfSubjectAccessReview access for this cluster.'
            ) from exc
        raise ValueError('KAORI could not validate ConfigMap delete authorization against Kubernetes.') from exc

    status = getattr(response, 'status', None)
    if not bool(getattr(status, 'allowed', False)):
        raise ValueError('Kubernetes denied ConfigMap deletion for this namespace. Verify ConfigMap delete RBAC.')


def delete_configmap(
    form: Any,
    *,
    validate_only: bool,
    expected_resource_version: str | None = None,
) -> dict[str, Any]:
    target = _bound_target(form)
    if form.get('confirm_name') != target.name:
        raise ValueError('Type the exact ConfigMap name to confirm deletion.')

    live = read_configmap(target)
    impact = get_impact_context(target)
    resource_version = str(live.get('resource_version') or '')
    if not resource_version:
        raise ValueError('Kubernetes did not return a ConfigMap resource version. Reload the target and retry.')
    if expected_resource_version and resource_version != expected_resource_version:
        raise ValueError('The ConfigMap changed after validation. Run deletion validation again.')

    if validate_only:
        _validate_delete_authorization(target)
    else:
        body = client.V1DeleteOptions(
            propagation_policy='Background',
            preconditions=client.V1Preconditions(resource_version=resource_version),
        )
        try:
            live_call(
                target.cluster,
                'delete operation',
                lambda api: api.delete_namespaced_config_map(
                    name=target.name,
                    namespace=target.namespace,
                    body=body,
                    _request_timeout=10,
                ),
            )
        except ApiException as exc:
            raise safe_api_error(exc, 'delete operation') from exc

    return {
        'cluster_id': target.cluster.id,
        'cluster_name': target.cluster.name,
        'namespace': target.namespace,
        'configmap_name': target.name,
        'key_names': sorted([*live['data'], *live['binary_data']]),
        'key_count': len(live['data']) + len(live['binary_data']),
        'impact_count': impact.count,
        'impact_collection_state': impact.collection_state,
        'resource_version': resource_version,
        'operation': 'validation' if validate_only else 'deletion',
        'validation_mode': 'authorization_preflight' if validate_only else 'validated_receipt',
        'live_target_source': True,
        'inventory_target_gate': False,
        'impact_context_source': 'latest_committed_pod_inventory',
    }
