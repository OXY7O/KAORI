from __future__ import annotations

from typing import Any, cast

from kubernetes.client import AuthorizationV1Api, CoreV1Api
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.integrations.kubernetes.resolver import connection_for_cluster, tls_policy_for_cluster
from app.integrations.kubernetes.tls import weak_tls_context
from app.integrations.registry import get_integration
from app.models.cluster import Cluster


def runtime_client(cluster: Cluster) -> Any:
    return get_integration('container_orchestrator').execute(
        'client.build',
        connection_for_cluster(cluster),
    )


def core_api(cluster: Cluster) -> CoreV1Api:
    return cast(CoreV1Api, runtime_client(cluster).core_api())


def authorization_api(cluster: Cluster) -> AuthorizationV1Api:
    return cast(AuthorizationV1Api, runtime_client(cluster).authorization_api())


def _call(cluster: Cluster, operation: str, factory: Any, callback: Any) -> Any:
    try:
        with weak_tls_context(enabled=tls_policy_for_cluster(cluster)[1]):
            return callback(factory(cluster))
    except ApiException:
        raise
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, TimeoutError, Urllib3HTTPError) as exc:
        raise ValueError(f'KAORI could not reach the Kubernetes API during the ConfigMap {operation}.') from exc


def live_call(cluster: Cluster, operation: str, callback: Any) -> Any:
    return _call(cluster, operation, core_api, callback)


def authorization_call(cluster: Cluster, operation: str, callback: Any) -> Any:
    return _call(cluster, operation, authorization_api, callback)


def safe_api_error(exc: ApiException, operation: str) -> ValueError:
    action = operation.strip().lower()
    if exc.status == 409:
        if action.startswith('create'):
            return ValueError('A ConfigMap with this name already exists. Existing data was not changed.')
        return ValueError('The ConfigMap changed concurrently. Reload the live object and retry the operation.')
    if exc.status == 404:
        return ValueError('The ConfigMap or namespace was not found in Kubernetes.')
    if exc.status == 403:
        return ValueError(f'Kubernetes denied the {operation}. Verify ConfigMap RBAC for this namespace.')
    if exc.status == 401:
        return ValueError('Kubernetes authentication failed for the cluster kubeconfig identity.')
    if exc.status == 422:
        return ValueError('Kubernetes rejected the ConfigMap payload because one or more fields are invalid.')
    return ValueError(f'Kubernetes could not complete the ConfigMap {operation}.')
