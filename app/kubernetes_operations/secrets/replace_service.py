from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.kubernetes.client import KubernetesClient
from app.kubernetes.tls import legacy_tls_context
from app.kubernetes_operations.secrets.replace_payloads import build_replace_patch
from app.models import Cluster, ConfigurationInventory, NamespaceInventory

SUPPORTED_REPLACE_TYPES = {
    'Opaque': {
        'key': 'opaque',
        'label': 'Generic / Opaque',
        'tone': 'blue',
        'icon': 'code',
    },
    'kubernetes.io/basic-auth': {
        'key': 'basic-auth',
        'label': 'Basic Authentication',
        'tone': 'violet',
        'icon': 'user',
    },
    'kubernetes.io/dockerconfigjson': {
        'key': 'dockerconfigjson',
        'label': 'Container Registry',
        'tone': 'cyan',
        'icon': 'boxes',
    },
    'kubernetes.io/ssh-auth': {
        'key': 'ssh-auth',
        'label': 'SSH Authentication',
        'tone': 'amber',
        'icon': 'key',
    },
}


@dataclass(frozen=True)
class SecretReplacementResult:
    status: str
    title: str
    message: str
    detail: str | None
    metadata: dict[str, Any]


def get_secret_replace_context() -> dict[str, Any]:
    return {
        'clusters': Cluster.query.order_by(Cluster.name.asc()).all(),
    }


def get_replace_workspace(
    cluster_id: str | None,
    namespace: str | None = None,
    inventory_id: str | int | None = None,
) -> dict[str, Any]:
    normalized_cluster_id = (cluster_id or '').strip()
    normalized_namespace = (namespace or '').strip()
    namespaces: list[str] = []
    targets: list[ConfigurationInventory] = []
    selected_target_id = str(inventory_id or '').strip()

    if normalized_cluster_id:
        namespaces = [
            value
            for (value,) in (
                NamespaceInventory.query.with_entities(NamespaceInventory.namespace)
                .filter(NamespaceInventory.cluster_id == normalized_cluster_id)
                .order_by(NamespaceInventory.namespace.asc())
                .all()
            )
        ]

    if normalized_cluster_id and normalized_namespace in namespaces:
        targets = (
            ConfigurationInventory.query.filter(
                ConfigurationInventory.cluster_id == normalized_cluster_id,
                ConfigurationInventory.namespace == normalized_namespace,
                ConfigurationInventory.object_type == 'Secret',
                ConfigurationInventory.secret_type.in_(tuple(SUPPORTED_REPLACE_TYPES)),
            )
            .order_by(ConfigurationInventory.name.asc())
            .all()
        )

    return {
        'cluster_id': normalized_cluster_id,
        'namespace': normalized_namespace if normalized_namespace in namespaces else '',
        'namespaces': namespaces,
        'targets': targets,
        'selected_target_id': selected_target_id,
        'replace_types': SUPPORTED_REPLACE_TYPES,
    }


def get_replace_target(inventory_id: str | int | None) -> ConfigurationInventory | None:
    normalized_id = str(inventory_id or '').strip()
    if not normalized_id.isdigit():
        return None
    return ConfigurationInventory.query.filter_by(
        id=int(normalized_id),
        object_type='Secret',
    ).first()


def get_replace_target_context(inventory_id: str | int | None) -> dict[str, Any]:
    target = get_replace_target(inventory_id)
    if target is None or target.secret_type not in SUPPORTED_REPLACE_TYPES:
        return {'target': None, 'type_config': None}
    return {
        'target': target,
        'type_config': SUPPORTED_REPLACE_TYPES[target.secret_type],
    }


def _required(value: str | None, label: str) -> str:
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} is required.')
    return normalized


def _api_error_message(exc: ApiException) -> str:
    status = getattr(exc, 'status', None)
    if status == 404:
        return 'The selected Secret no longer exists in Kubernetes. Refresh inventory before retrying.'
    if status == 403:
        return 'Kubernetes denied this update. Verify the cluster credential can patch Secrets in the namespace.'
    if status == 401:
        return 'Kubernetes authentication failed for the selected cluster.'
    if status == 409:
        return 'Kubernetes reported a resource conflict. Refresh inventory and retry the replacement.'
    if status == 422:
        return 'Kubernetes rejected the patch. The Secret may be immutable or the submitted data may be invalid.'
    if status == 400:
        return 'Kubernetes rejected the Secret patch request.'
    return 'Kubernetes API rejected the Secret data replacement.'


def _close_api_response(response: Any) -> None:
    if response is None:
        return
    release_conn = getattr(response, 'release_conn', None)
    close = getattr(response, 'close', None)
    if callable(close):
        close()
    if callable(release_conn):
        release_conn()


def _patch_secret(
    *,
    cluster: Cluster,
    target: ConfigurationInventory,
    string_data: dict[str, str],
    dry_run: bool,
) -> None:
    encoded_data = {
        key: base64.b64encode(value.encode('utf-8')).decode('ascii')
        for key, value in string_data.items()
    }
    body = {'data': encoded_data}

    with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
        api = KubernetesClient(
            cluster.kubeconfig,
            verify_ssl=bool(cluster.kube_verify_ssl),
        ).core_api()
        response = api.patch_namespaced_secret(
            name=target.name,
            namespace=target.namespace,
            body=body,
            dry_run='All' if dry_run else None,
            field_manager='kaori-secret-management',
            _preload_content=False,
        )
        _close_api_response(response)


def execute_secret_replacement(
    form: Any,
    files: Any,
    *,
    dry_run: bool,
) -> SecretReplacementResult:
    inventory_id = _required(form.get('inventory_id'), 'Secret target')
    target = get_replace_target(inventory_id)
    if target is None:
        raise ValueError('Selected Secret inventory record was not found.')
    if target.secret_type not in SUPPORTED_REPLACE_TYPES:
        raise ValueError('This Secret type is not supported by the replacement workflow.')

    submitted_cluster_id = _required(form.get('cluster_id'), 'Cluster')
    submitted_namespace = _required(form.get('namespace'), 'Namespace')
    if submitted_cluster_id != str(target.cluster_id) or submitted_namespace != target.namespace:
        raise ValueError(
            'The submitted cluster or namespace does not match the selected Secret snapshot. '
            'Select the target again before continuing.'
        )

    if target.immutable:
        raise ValueError('Immutable Secrets cannot be updated. Create a replacement Secret instead.')

    cluster = Cluster.query.filter_by(id=target.cluster_id).first()
    if cluster is None:
        raise ValueError('The target cluster record no longer exists.')

    patch_data = build_replace_patch(form, files, target)
    if not dry_run and (form.get('confirm_replace') or '').strip().lower() != 'yes':
        raise ValueError('Confirm the selected-key replacement before applying changes.')

    try:
        # Apply always performs the same server-side dry-run immediately before mutation.
        _patch_secret(
            cluster=cluster,
            target=target,
            string_data=patch_data,
            dry_run=True,
        )
        if not dry_run:
            _patch_secret(
                cluster=cluster,
                target=target,
                string_data=patch_data,
                dry_run=False,
            )
    except ApiException as exc:
        raise ValueError(_api_error_message(exc)) from exc
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            'KAORI could not reach the Kubernetes API for the selected cluster. '
            'Check connectivity and cluster configuration.'
        ) from exc

    operation = 'validation' if dry_run else 'replacement'
    type_config = SUPPORTED_REPLACE_TYPES[target.secret_type]
    return SecretReplacementResult(
        status='success',
        title=(
            'Secret replacement validation completed'
            if dry_run
            else 'Secret data replacement completed'
        ),
        message=(
            f'{target.name} is valid and ready to update in {cluster.name}/{target.namespace}.'
            if dry_run
            else f'{target.name} was updated in {cluster.name}/{target.namespace}.'
        ),
        detail=None,
        metadata={
            'configuration_inventory_id': target.id,
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'namespace': target.namespace,
            'secret_name': target.name,
            'secret_type': target.secret_type,
            'secret_type_label': type_config['label'],
            'operation': operation,
            'updated_key_names': sorted(patch_data),
            'updated_key_count': len(patch_data),
            'existing_values_read': False,
        },
    )
