from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, cast

from kubernetes.client import CoreV1Api, V1NamespaceList, V1Secret, V1SecretList
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.kubernetes.client import KubernetesClient
from app.kubernetes.tls import legacy_tls_context
from app.models import Cluster, ConfigurationInventory

_DNS_LABEL = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
_DNS_SUBDOMAIN = re.compile(r"^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$")


@dataclass(frozen=True)
class LiveSecretOption:
    name: str
    secret_type: str
    immutable: bool


@dataclass(frozen=True)
class LiveSecretSnapshot:
    cluster: Cluster
    namespace: str
    name: str
    secret_type: str
    immutable: bool
    key_names: tuple[str, ...]
    uid: str | None
    resource_version: str | None

    @property
    def cluster_id(self) -> str:
        return str(self.cluster.id)

    @property
    def cluster_name(self) -> str:
        return self.cluster.name

    @property
    def key_count(self) -> int:
        return len(self.key_names)


def get_cluster(cluster_id: str | None) -> Cluster:
    normalized = (cluster_id or "").strip()
    if not normalized:
        raise ValueError("Cluster is required.")
    cluster = Cluster.query.filter_by(id=normalized).first()
    if cluster is None:
        raise ValueError("The selected Kubernetes cluster is no longer available.")
    return cluster


def core_api(cluster: Cluster) -> CoreV1Api:
    return KubernetesClient(
        cluster.kubeconfig,
        verify_ssl=bool(cluster.kube_verify_ssl),
    ).core_api()


def validate_resource_name(
    value: str | None, label: str, *, namespace: bool = False
) -> str:
    normalized = (value or "").strip()
    max_length = 63 if namespace else 253
    pattern = _DNS_LABEL if namespace else _DNS_SUBDOMAIN
    if (
        not normalized
        or len(normalized) > max_length
        or not pattern.fullmatch(normalized)
    ):
        qualifier = "namespace name" if namespace else "DNS subdomain"
        raise ValueError(f"{label} must be a valid Kubernetes {qualifier}.")
    return normalized


def _scrub_secret(secret: Any) -> None:
    """Best-effort removal of payload material from in-memory Kubernetes objects."""
    for attribute in ("data", "string_data"):
        value = getattr(secret, attribute, None)
        if isinstance(value, dict):
            for key in list(value):
                value[key] = ""
            value.clear()
        try:
            setattr(secret, attribute, None)
        except (AttributeError, TypeError):
            pass


def _api_error(exc: ApiException, operation: str) -> ValueError:
    status = getattr(exc, "status", None)
    if status == 404:
        return ValueError(
            f"The selected Kubernetes namespace or Secret no longer exists during {operation}."
        )
    if status == 403:
        return ValueError(
            f"Kubernetes denied the live Secret {operation}. Verify Secret RBAC for this namespace."
        )
    if status == 401:
        return ValueError("Kubernetes authentication failed for the selected cluster.")
    if status == 409:
        return ValueError(
            f"Kubernetes reported a resource conflict during Secret {operation}. Reload the live target and retry."
        )
    if status == 422:
        return ValueError(f"Kubernetes rejected the Secret {operation} request.")
    if status == 429:
        return ValueError(
            "Kubernetes temporarily rate-limited the Secret request. Retry later."
        )
    return ValueError(f"Kubernetes API could not complete the Secret {operation}.")


def _connection_error(operation: str) -> ValueError:
    return ValueError(
        f"KAORI could not reach the Kubernetes API while performing the live Secret {operation}. "
        "Check cluster connectivity and kubeconfig settings."
    )


def list_live_namespaces(
    cluster_id: str | None,
    *,
    allowed_namespaces: Iterable[str] | None = None,
) -> list[str]:
    normalized = (cluster_id or "").strip()
    if not normalized:
        return []
    cluster = get_cluster(normalized)
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            response = cast(V1NamespaceList, core_api(cluster).list_namespace())
    except ApiException as exc:
        raise _api_error(exc, "namespace lookup") from exc
    except ConfigException as exc:
        raise ValueError(
            "The selected cluster kubeconfig is invalid or incomplete."
        ) from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise _connection_error("namespace lookup") from exc

    names = {
        item.metadata.name
        for item in (response.items or [])
        if getattr(getattr(item, "metadata", None), "name", None)
    }
    if allowed_namespaces is not None:
        names.intersection_update(
            value.strip() for value in allowed_namespaces if value and value.strip()
        )
    return sorted(names)


def verify_live_namespace(cluster: Cluster, namespace: str | None) -> str:
    normalized = validate_resource_name(namespace, "Namespace", namespace=True)
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            core_api(cluster).read_namespace(name=normalized)
    except ApiException as exc:
        raise _api_error(exc, "namespace verification") from exc
    except ConfigException as exc:
        raise ValueError(
            "The selected cluster kubeconfig is invalid or incomplete."
        ) from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise _connection_error("namespace verification") from exc
    return normalized


def list_live_secrets(
    cluster_id: str | None,
    namespace: str | None,
    *,
    supported_types: set[str] | frozenset[str] | None = None,
    blocked_types: set[str] | frozenset[str] | None = None,
) -> list[LiveSecretOption]:
    normalized_cluster_id = (cluster_id or "").strip()
    normalized_namespace = (namespace or "").strip()
    if not normalized_cluster_id or not normalized_namespace:
        return []

    cluster = get_cluster(normalized_cluster_id)
    normalized_namespace = validate_resource_name(
        normalized_namespace,
        "Namespace",
        namespace=True,
    )
    response: V1SecretList | None = None
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            response = cast(
                V1SecretList,
                core_api(cluster).list_namespaced_secret(
                    namespace=normalized_namespace,
                    _request_timeout=10,
                ),
            )
        options: list[LiveSecretOption] = []
        for item in response.items or []:
            name = getattr(getattr(item, "metadata", None), "name", None)
            secret_type = str(getattr(item, "type", None) or "Opaque")
            if not name:
                continue
            if supported_types is not None and secret_type not in supported_types:
                continue
            if blocked_types is not None and secret_type in blocked_types:
                continue
            options.append(
                LiveSecretOption(
                    name=name,
                    secret_type=secret_type,
                    immutable=bool(getattr(item, "immutable", False)),
                )
            )
        return sorted(options, key=lambda item: item.name)
    except ApiException as exc:
        raise _api_error(exc, "list operation") from exc
    except ConfigException as exc:
        raise ValueError(
            "The selected cluster kubeconfig is invalid or incomplete."
        ) from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise _connection_error("list operation") from exc
    finally:
        if response is not None:
            for item in response.items or []:
                _scrub_secret(item)


def read_live_secret(
    cluster_id: str | None,
    namespace: str | None,
    secret_name: str | None,
    *,
    supported_types: set[str] | frozenset[str] | None = None,
    blocked_types: set[str] | frozenset[str] | None = None,
) -> LiveSecretSnapshot:
    cluster = get_cluster(cluster_id)
    normalized_namespace = validate_resource_name(
        namespace,
        "Namespace",
        namespace=True,
    )
    normalized_name = validate_resource_name(secret_name, "Secret name")
    secret: V1Secret | None = None
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            secret = cast(
                V1Secret,
                core_api(cluster).read_namespaced_secret(
                    name=normalized_name,
                    namespace=normalized_namespace,
                    _request_timeout=10,
                ),
            )
        secret_type = str(getattr(secret, "type", None) or "Opaque")
        if supported_types is not None and secret_type not in supported_types:
            raise ValueError(
                "This live Secret type is not supported by the selected workflow."
            )
        if blocked_types is not None and secret_type in blocked_types:
            raise ValueError(
                "This live Secret type is blocked from the selected workflow."
            )
        data = getattr(secret, "data", None) or {}
        string_data = getattr(secret, "string_data", None) or {}
        key_names = tuple(
            sorted(
                {
                    str(key).strip()
                    for key in [*data.keys(), *string_data.keys()]
                    if str(key).strip()
                }
            )
        )
        metadata = getattr(secret, "metadata", None)
        return LiveSecretSnapshot(
            cluster=cluster,
            namespace=normalized_namespace,
            name=normalized_name,
            secret_type=secret_type,
            immutable=bool(getattr(secret, "immutable", False)),
            key_names=key_names,
            uid=getattr(metadata, "uid", None),
            resource_version=getattr(metadata, "resource_version", None),
        )
    except ApiException as exc:
        raise _api_error(exc, "read operation") from exc
    except ConfigException as exc:
        raise ValueError(
            "The selected cluster kubeconfig is invalid or incomplete."
        ) from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise _connection_error("read operation") from exc
    finally:
        if secret is not None:
            _scrub_secret(secret)


def best_effort_inventory_id(target: LiveSecretSnapshot) -> int | None:
    record = ConfigurationInventory.query.filter_by(
        cluster_id=target.cluster.id,
        namespace=target.namespace,
        name=target.name,
        object_type="Secret",
    ).first()
    return record.id if record is not None else None
