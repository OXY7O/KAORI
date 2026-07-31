from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kubernetes import client
from kubernetes.client import V1DeleteOptions, V1Preconditions
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.integrations.kubernetes.resolver import tls_policy_for_cluster
from app.integrations.kubernetes.tls import weak_tls_context
from app.kubernetes_operations.secrets.live_service import (
    LiveSecretSnapshot,
    authorization_api,
    core_api,
    list_live_namespaces,
    list_live_secrets,
    read_live_secret,
)
from app.models import Cluster, PodInventory

BLOCKED_DELETE_TYPES = {'kubernetes.io/service-account-token'}


@dataclass(frozen=True)
class SecretDeletionResult:
    status: str
    title: str
    message: str
    detail: str | None
    metadata: dict[str, Any]


def get_secret_delete_context() -> dict[str, Any]:
    return {'clusters': Cluster.query.order_by(Cluster.name.asc()).all()}


def get_delete_workspace(
    cluster_id: str | None,
    namespace: str | None = None,
    secret_name: str | None = None,
) -> dict[str, Any]:
    normalized_cluster_id = (cluster_id or '').strip()
    normalized_namespace = (namespace or '').strip()
    selected_secret_name = (secret_name or '').strip()
    namespaces: list[str] = []
    targets = []
    selection_error = None
    selection_error_title = None

    if normalized_cluster_id:
        try:
            namespaces = list_live_namespaces(normalized_cluster_id)
        except ValueError as exc:
            selection_error = str(exc)
            selection_error_title = 'Live namespace lookup failed'
            normalized_namespace = ''
            selected_secret_name = ''
        else:
            if normalized_namespace not in namespaces:
                normalized_namespace = ''
                selected_secret_name = ''
            if normalized_namespace:
                try:
                    targets = list_live_secrets(
                        normalized_cluster_id,
                        normalized_namespace,
                        blocked_types=BLOCKED_DELETE_TYPES,
                    )
                except ValueError as exc:
                    selection_error = str(exc)
                    selection_error_title = 'Live Secret lookup failed'
                    selected_secret_name = ''
                else:
                    live_names = {item.name for item in targets}
                    if selected_secret_name not in live_names:
                        selected_secret_name = ''

    return {
        'cluster_id': normalized_cluster_id,
        'namespace': normalized_namespace,
        'namespaces': namespaces,
        'targets': targets,
        'selected_secret_name': selected_secret_name,
        'selection_error': selection_error,
        'selection_error_title': selection_error_title,
    }


def get_secret_impact_context(target: LiveSecretSnapshot) -> list[dict[str, str]]:
    pods = PodInventory.query.filter_by(
        cluster_id=target.cluster.id,
        namespace=target.namespace,
    ).all()
    impacts: dict[tuple[str, str], dict[str, str]] = {}
    for pod in pods:
        references = pod.configuration_references or []
        if not any(
            ref.get('type') == 'Secret' and ref.get('name') == target.name
            for ref in references
        ):
            continue
        kind = pod.workload_type or 'Pod'
        name = pod.workload_name or pod.pod_name
        impacts[(kind, name)] = {
            'kind': kind,
            'name': name,
            'supporting_primary': f'{kind} workload',
            'supporting_secondary': 'Committed inventory reference',
            'status': None,
            'status_tone': None,
        }
    return sorted(impacts.values(), key=lambda item: (item['kind'], item['name']))


def get_delete_target_context(
    cluster_id: str | None,
    namespace: str | None,
    secret_name: str | None,
) -> dict[str, Any]:
    if not all(
        (
            (cluster_id or '').strip(),
            (namespace or '').strip(),
            (secret_name or '').strip(),
        )
    ):
        return {'target': None, 'impacts': [], 'target_error': None}
    try:
        target = read_live_secret(
            cluster_id,
            namespace,
            secret_name,
            blocked_types=BLOCKED_DELETE_TYPES,
        )
    except ValueError as exc:
        return {'target': None, 'impacts': [], 'target_error': str(exc)}
    return {
        'target': target,
        'impacts': get_secret_impact_context(target),
        'target_error': None,
    }


def _required(value: str | None, label: str) -> str:
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} is required.')
    return normalized


def _bound_target(form: Any) -> LiveSecretSnapshot:
    selected = (
        _required(form.get('cluster_id'), 'Cluster'),
        _required(form.get('namespace'), 'Namespace'),
        _required(form.get('secret_name'), 'Secret target'),
    )
    bound = (
        _required(form.get('target_cluster_id'), 'Bound cluster'),
        _required(form.get('target_namespace'), 'Bound namespace'),
        _required(form.get('target_secret_name'), 'Bound Secret target'),
    )
    if selected != bound:
        raise ValueError(
            'The Secret selection changed after the deletion review was loaded. '
            'Reload the target and retry.'
        )
    return read_live_secret(*bound, blocked_types=BLOCKED_DELETE_TYPES)


def _api_error_message(exc: ApiException) -> str:
    status = getattr(exc, 'status', None)
    if status == 404:
        return 'The selected Secret no longer exists in Kubernetes. Reload the live target.'
    if status == 403:
        return 'Kubernetes denied this deletion. Verify Secret delete RBAC for the namespace.'
    if status == 401:
        return 'Kubernetes authentication failed for the selected cluster.'
    if status == 409:
        return 'The live Secret changed after review. Reload the target before deleting it.'
    if status == 422:
        return 'Kubernetes rejected the Secret deletion request.'
    return 'Kubernetes API could not complete the Secret deletion.'


def _validate_delete_authorization(target: LiveSecretSnapshot) -> None:
    review = client.V1SelfSubjectAccessReview(
        spec=client.V1SelfSubjectAccessReviewSpec(
            resource_attributes=client.V1ResourceAttributes(
                group='',
                resource='secrets',
                verb='delete',
                namespace=target.namespace,
                name=target.name,
            )
        )
    )
    try:
        with weak_tls_context(enabled=tls_policy_for_cluster(target.cluster)[1]):
            response = authorization_api(
                target.cluster
            ).create_self_subject_access_review(
                body=review,
                _request_timeout=10,
            )
    except ApiException as exc:
        if exc.status == 401:
            raise ValueError(
                'Kubernetes authentication failed while validating Secret delete access.'
            ) from exc
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied the delete authorization preflight. '
                'Verify SelfSubjectAccessReview access for this cluster.'
            ) from exc
        raise ValueError(
            'KAORI could not validate Secret delete authorization against Kubernetes.'
        ) from exc
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            'KAORI could not reach the Kubernetes API while validating Secret delete access.'
        ) from exc

    status = getattr(response, 'status', None)
    if not bool(getattr(status, 'allowed', False)):
        raise ValueError(
            'Kubernetes denied Secret deletion for this namespace. Verify Secret delete RBAC.'
        )


def execute_secret_deletion(
    form: Any,
    *,
    validate_only: bool,
    expected_resource_version: str | None = None,
) -> SecretDeletionResult:
    target = _bound_target(form)
    if _required(form.get('confirm_name'), 'Exact Secret name') != target.name:
        raise ValueError('Type the exact live Secret name to confirm deletion.')

    resource_version = str(target.resource_version or '')
    if not resource_version:
        raise ValueError(
            'Kubernetes did not return a Secret resource version. Reload the target and retry.'
        )
    if expected_resource_version and resource_version != expected_resource_version:
        raise ValueError('The Secret changed after validation. Run deletion validation again.')

    impacts = get_secret_impact_context(target)

    try:
        if validate_only:
            # Validation deliberately avoids the Secret DELETE endpoint. Some older
            # or proxied Kubernetes environments do not enforce DELETE dryRun
            # consistently, so authorization is checked through SSAR instead.
            _validate_delete_authorization(target)
        else:
            body = V1DeleteOptions(
                propagation_policy='Background',
                preconditions=V1Preconditions(resource_version=resource_version),
            )
            with weak_tls_context(enabled=tls_policy_for_cluster(target.cluster)[1]):
                core_api(target.cluster).delete_namespaced_secret(
                    name=target.name,
                    namespace=target.namespace,
                    body=body,
                    _request_timeout=10,
                )
    except ApiException as exc:
        raise ValueError(_api_error_message(exc)) from exc
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        operation = (
            'validating Secret delete access'
            if validate_only
            else 'deleting the live Secret'
        )
        raise ValueError(f'KAORI could not reach the Kubernetes API while {operation}.') from exc

    operation = 'validation' if validate_only else 'deletion'
    return SecretDeletionResult(
        status='success',
        title=(
            'Secret deletion validation completed'
            if validate_only
            else 'Secret deleted'
        ),
        message=(
            'KAORI verified the live Secret identity, resource version, and effective '
            'delete authorization without sending a DELETE request.'
            if validate_only
            else f'{target.name} was deleted from {target.cluster_name}/{target.namespace}.'
        ),
        detail=None,
        metadata={
            'cluster_id': target.cluster_id,
            'cluster_name': target.cluster_name,
            'namespace': target.namespace,
            'secret_name': target.name,
            'secret_type': target.secret_type,
            'key_names': list(target.key_names),
            'key_count': target.key_count,
            'impact_count': len(impacts),
            'resource_version': resource_version,
            'operation': operation,
            'validation_mode': (
                'authorization_preflight' if validate_only else 'validated_receipt'
            ),
            'live_target_source': True,
            'secret_value_recorded': False,
        },
    )
