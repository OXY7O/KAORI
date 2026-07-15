from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any

from kubernetes import client
from kubernetes.client import ApiException
from sqlalchemy import and_

from app.models.cluster import Cluster
from app.kubernetes.client import KubernetesClient
from app.models.inventory import ConfigurationInventory, PodInventory

_DNS_SUBDOMAIN = re.compile(r'^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$')
_KEY_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
_MAX_PAYLOAD = 1024 * 1024


@dataclass(frozen=True)
class ConfigMapTarget:
    inventory: ConfigurationInventory
    cluster: Cluster


def _cluster(cluster_id: str) -> Cluster:
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        raise ValueError('The selected Kubernetes cluster is no longer available.')
    return cluster


def get_context() -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    total = ConfigurationInventory.query.filter_by(object_type='ConfigMap').count()
    namespace_count = (
        ConfigurationInventory.query.with_entities(ConfigurationInventory.namespace)
        .filter_by(object_type='ConfigMap').distinct().count()
    )
    immutable_count = ConfigurationInventory.query.filter_by(
        object_type='ConfigMap', immutable=True
    ).count()
    return {
        'clusters': clusters,
        'total_configmaps': total,
        'namespace_count': namespace_count,
        'immutable_count': immutable_count,
    }


def get_namespaces(cluster_id: str) -> list[str]:
    """Return the current namespace list directly from the selected cluster.

    Operational ConfigMap workflows intentionally do not use inventory snapshots
    for namespace selection because create/delete operations can make inventory
    stale until the next synchronization.
    """
    if not cluster_id:
        return []
    cluster = _cluster(cluster_id)
    try:
        response = _api(cluster).list_namespace()
    except ApiException as exc:
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied the live namespace lookup. Verify namespace list RBAC for this cluster.'
            ) from exc
        if exc.status == 401:
            raise ValueError(
                'Kubernetes authentication failed while loading live namespaces.'
            ) from exc
        raise ValueError(
            'KAORI could not load live namespaces from the selected Kubernetes cluster.'
        ) from exc
    return sorted(
        item.metadata.name
        for item in (response.items or [])
        if getattr(getattr(item, 'metadata', None), 'name', None)
    )


def get_configmaps(cluster_id: str, namespace: str) -> list[ConfigurationInventory]:
    if not cluster_id or not namespace:
        return []
    return ConfigurationInventory.query.filter_by(
        cluster_id=cluster_id,
        namespace=namespace,
        object_type='ConfigMap',
    ).order_by(ConfigurationInventory.name.asc()).all()


def get_target(inventory_id: int) -> ConfigMapTarget:
    record = ConfigurationInventory.query.filter_by(
        id=inventory_id,
        object_type='ConfigMap',
    ).first()
    if record is None:
        raise ValueError('The selected ConfigMap is no longer available in inventory.')
    return ConfigMapTarget(inventory=record, cluster=_cluster(record.cluster_id))


def _validate_name(value: str, label: str) -> str:
    value = (value or '').strip()
    if not value or len(value) > 253 or not _DNS_SUBDOMAIN.fullmatch(value):
        raise ValueError(f'{label} must be a valid Kubernetes DNS subdomain.')
    return value


def _validate_namespace(value: str, cluster_id: str) -> str:
    value = _validate_name(value, 'Namespace')
    cluster = _cluster(cluster_id)
    try:
        _api(cluster).read_namespace(name=value)
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError(
                'The selected namespace no longer exists in the Kubernetes cluster.'
            ) from exc
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied namespace verification. Verify namespace read RBAC for this cluster.'
            ) from exc
        if exc.status == 401:
            raise ValueError(
                'Kubernetes authentication failed while verifying the namespace.'
            ) from exc
        raise ValueError(
            'KAORI could not verify the selected namespace against the live Kubernetes cluster.'
        ) from exc
    return value


def _parse_entries(form: Any) -> tuple[dict[str, str], dict[str, bytes]]:
    keys = form.getlist('entry_key')
    values = form.getlist('entry_value')
    kinds = form.getlist('entry_kind')
    data: dict[str, str] = {}
    binary_data: dict[str, bytes] = {}
    for index, raw_key in enumerate(keys):
        key = (raw_key or '').strip()
        if not key:
            continue
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError(f'ConfigMap key "{key}" contains unsupported characters.')
        if key in data or key in binary_data:
            raise ValueError(f'ConfigMap key "{key}" is duplicated.')
        value = values[index] if index < len(values) else ''
        kind = kinds[index] if index < len(kinds) else 'text'
        if kind == 'binary':
            try:
                binary_data[key] = base64.b64decode(value, validate=True)
            except Exception as exc:
                raise ValueError(f'Binary key "{key}" must contain valid base64 data.') from exc
        else:
            data[key] = value
    if not data and not binary_data:
        raise ValueError('Add at least one ConfigMap key before validating.')
    payload_size = sum(len(k.encode()) + len(v.encode()) for k, v in data.items())
    payload_size += sum(len(k.encode()) + len(v) for k, v in binary_data.items())
    if payload_size > _MAX_PAYLOAD:
        raise ValueError('The ConfigMap payload exceeds the Kubernetes 1 MiB object limit.')
    return data, binary_data


def _api(cluster: Cluster):
    return KubernetesClient(cluster.kubeconfig).core_api()


def _safe_api_error(exc: ApiException, operation: str) -> ValueError:
    if exc.status == 409:
        return ValueError('A ConfigMap with this name already exists. Existing data was not changed.')
    if exc.status == 404:
        return ValueError('The ConfigMap or namespace was not found in Kubernetes.')
    if exc.status == 403:
        return ValueError(f'Kubernetes denied the {operation}. Verify ConfigMap RBAC for this namespace.')
    if exc.status == 401:
        return ValueError('Kubernetes authentication failed for the cluster kubeconfig identity.')
    if exc.status == 422:
        return ValueError('Kubernetes rejected the ConfigMap payload because one or more fields are invalid.')
    return ValueError(f'Kubernetes could not complete the ConfigMap {operation}.')


def create_configmap(form: Any, *, dry_run: bool) -> dict[str, Any]:
    cluster_id = (form.get('cluster_id') or '').strip()
    cluster = _cluster(cluster_id)
    namespace = _validate_namespace(form.get('namespace') or '', cluster_id)
    name = _validate_name(form.get('configmap_name') or '', 'ConfigMap name')
    data, binary_data = _parse_entries(form)
    body = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=name, namespace=namespace),
        data=data or None,
        binary_data=binary_data or None,
        immutable=form.get('immutable') == 'true',
    )
    try:
        result = _api(cluster).create_namespaced_config_map(
            namespace=namespace,
            body=body,
            dry_run='All' if dry_run else None,
        )
    except ApiException as exc:
        raise _safe_api_error(exc, 'create operation') from exc
    return {
        'cluster_id': cluster.id,
        'cluster_name': cluster.name,
        'namespace': namespace,
        'configmap_name': name,
        'key_names': sorted([*data.keys(), *binary_data.keys()]),
        'immutable': bool(body.immutable),
        'resource_version': getattr(getattr(result, 'metadata', None), 'resource_version', None),
    }


def read_configmap(target: ConfigMapTarget) -> dict[str, Any]:
    try:
        obj = _api(target.cluster).read_namespaced_config_map(
            name=target.inventory.name,
            namespace=target.inventory.namespace,
        )
    except ApiException as exc:
        raise _safe_api_error(exc, 'read operation') from exc
    data = dict(sorted((obj.data or {}).items()))
    binary_data = {
        key: base64.b64encode(value).decode() if isinstance(value, bytes) else str(value)
        for key, value in sorted((obj.binary_data or {}).items())
    }
    return {
        'data': data,
        'binary_data': binary_data,
        'immutable': bool(obj.immutable),
        'resource_version': getattr(obj.metadata, 'resource_version', None),
    }


def get_impact_context(target: ConfigMapTarget) -> list[dict[str, str]]:
    pods = PodInventory.query.filter_by(
        cluster_id=target.inventory.cluster_id,
        namespace=target.inventory.namespace,
    ).all()
    impacts: dict[tuple[str, str], dict[str, str]] = {}
    for pod in pods:
        references = pod.configuration_references or []
        if not any(
            ref.get('type') == 'ConfigMap' and ref.get('name') == target.inventory.name
            for ref in references
        ):
            continue
        kind = pod.workload_type or 'Pod'
        name = pod.workload_name or pod.pod_name
        impacts[(kind, name)] = {'kind': kind, 'name': name}
    return sorted(impacts.values(), key=lambda item: (item['kind'], item['name']))


def _submitted_update(form: Any, existing: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], str]:
    mode = (form.get('update_mode') or 'merge').strip()
    submitted_data, submitted_binary_raw = _parse_entries(form)
    submitted_binary = {k: base64.b64encode(v).decode() for k, v in submitted_binary_raw.items()}
    if mode == 'replace':
        return submitted_data, submitted_binary, mode
    merged_data = dict(existing['data'])
    merged_binary = dict(existing['binary_data'])
    for key, value in submitted_data.items():
        merged_binary.pop(key, None)
        merged_data[key] = value
    for key, value in submitted_binary.items():
        merged_data.pop(key, None)
        merged_binary[key] = value
    return merged_data, merged_binary, 'merge'


def _diff(existing: dict[str, Any], proposed_data: dict[str, str], proposed_binary: dict[str, str]) -> dict[str, list[str]]:
    old = {**{k: ('text', v) for k, v in existing['data'].items()}, **{k: ('binary', v) for k, v in existing['binary_data'].items()}}
    new = {**{k: ('text', v) for k, v in proposed_data.items()}, **{k: ('binary', v) for k, v in proposed_binary.items()}}
    return {
        'added': sorted(set(new) - set(old)),
        'changed': sorted(k for k in set(old) & set(new) if old[k] != new[k]),
        'removed': sorted(set(old) - set(new)),
        'unchanged': sorted(k for k in set(old) & set(new) if old[k] == new[k]),
    }


def update_configmap(form: Any, *, dry_run: bool) -> dict[str, Any]:
    inventory_id = int(form.get('inventory_id') or 0)
    target = get_target(inventory_id)
    if form.get('cluster_id') != target.inventory.cluster_id or form.get('namespace') != target.inventory.namespace:
        raise ValueError('The submitted ConfigMap target does not match inventory.')
    existing = read_configmap(target)
    if existing['immutable'] or target.inventory.immutable:
        raise ValueError('This ConfigMap is immutable and cannot be updated. Create a new ConfigMap instead.')
    proposed_data, proposed_binary, mode = _submitted_update(form, existing)
    diff = _diff(existing, proposed_data, proposed_binary)
    if not diff['added'] and not diff['changed'] and not diff['removed']:
        raise ValueError('No ConfigMap changes were detected.')
    if mode == 'replace' and form.get('confirm_replace') != 'yes':
        raise ValueError('Confirm full replacement before applying this update mode.')

    data_patch: dict[str, Any] = {}
    binary_patch: dict[str, Any] = {}
    for key in diff['added'] + diff['changed']:
        if key in proposed_data:
            data_patch[key] = proposed_data[key]
            if key in existing['binary_data']:
                binary_patch[key] = None
        else:
            binary_patch[key] = proposed_binary[key]
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
    try:
        result = _api(target.cluster).patch_namespaced_config_map(
            name=target.inventory.name,
            namespace=target.inventory.namespace,
            body=body,
            dry_run='All' if dry_run else None,
        )
    except ApiException as exc:
        raise _safe_api_error(exc, 'update operation') from exc
    return {
        'cluster_id': target.cluster.id,
        'cluster_name': target.cluster.name,
        'namespace': target.inventory.namespace,
        'configmap_name': target.inventory.name,
        'mode': mode,
        'diff': diff,
        'resource_version': getattr(getattr(result, 'metadata', None), 'resource_version', None),
        'impact_count': len(get_impact_context(target)),
    }


def delete_configmap(form: Any, *, dry_run: bool) -> dict[str, Any]:
    inventory_id = int(form.get('inventory_id') or 0)
    target = get_target(inventory_id)
    if form.get('confirm_name') != target.inventory.name:
        raise ValueError('Type the exact ConfigMap name to confirm deletion.')
    impacts = get_impact_context(target)
    body = client.V1DeleteOptions(propagation_policy='Background')
    try:
        _api(target.cluster).delete_namespaced_config_map(
            name=target.inventory.name,
            namespace=target.inventory.namespace,
            body=body,
            dry_run='All' if dry_run else None,
        )
    except ApiException as exc:
        raise _safe_api_error(exc, 'delete operation') from exc
    return {
        'cluster_id': target.cluster.id,
        'cluster_name': target.cluster.name,
        'namespace': target.inventory.namespace,
        'configmap_name': target.inventory.name,
        'key_names': sorted(target.inventory.key_names or []),
        'impact_count': len(impacts),
    }
