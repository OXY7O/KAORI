from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.kubernetes.tls import legacy_tls_context
from app.kubernetes_operations.secrets.live_service import (
    LiveSecretSnapshot,
    core_api,
    list_live_namespaces,
    list_live_secrets,
    read_live_secret,
)
from app.kubernetes_operations.secrets.replace_payloads import build_replace_patch
from app.models import Cluster

SUPPORTED_REPLACE_TYPES = {
    "Opaque": {
        "key": "opaque",
        "label": "Generic / Opaque",
        "tone": "violet",
        "icon": "code",
    },
    "kubernetes.io/basic-auth": {
        "key": "basic-auth",
        "label": "Basic Authentication",
        "tone": "violet",
        "icon": "user",
    },
    "kubernetes.io/dockerconfigjson": {
        "key": "dockerconfigjson",
        "label": "Container Registry",
        "tone": "violet",
        "icon": "boxes",
    },
    "kubernetes.io/ssh-auth": {
        "key": "ssh-auth",
        "label": "SSH Authentication",
        "tone": "warning",
        "icon": "key",
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
        "clusters": Cluster.query.order_by(Cluster.name.asc()).all(),
    }


def get_replace_workspace(
    cluster_id: str | None,
    namespace: str | None = None,
    secret_name: str | None = None,
) -> dict[str, Any]:
    normalized_cluster_id = (cluster_id or "").strip()
    normalized_namespace = (namespace or "").strip()
    selected_secret_name = (secret_name or "").strip()
    namespaces: list[str] = []
    targets = []
    selection_error = None

    if normalized_cluster_id:
        try:
            namespaces = list_live_namespaces(normalized_cluster_id)
            if normalized_namespace not in namespaces:
                normalized_namespace = ""
                selected_secret_name = ""
            if normalized_namespace:
                targets = list_live_secrets(
                    normalized_cluster_id,
                    normalized_namespace,
                    supported_types=set(SUPPORTED_REPLACE_TYPES),
                )
                live_names = {item.name for item in targets}
                if selected_secret_name not in live_names:
                    selected_secret_name = ""
        except ValueError as exc:
            selection_error = str(exc)
            normalized_namespace = ""
            selected_secret_name = ""

    return {
        "cluster_id": normalized_cluster_id,
        "namespace": normalized_namespace,
        "namespaces": namespaces,
        "targets": targets,
        "selected_secret_name": selected_secret_name,
        "selection_error": selection_error,
        "replace_types": SUPPORTED_REPLACE_TYPES,
    }


def get_replace_target_context(
    cluster_id: str | None,
    namespace: str | None,
    secret_name: str | None,
) -> dict[str, Any]:
    if not all(
        (
            (cluster_id or "").strip(),
            (namespace or "").strip(),
            (secret_name or "").strip(),
        )
    ):
        return {"target": None, "type_config": None, "target_error": None}
    try:
        target = read_live_secret(
            cluster_id,
            namespace,
            secret_name,
            supported_types=set(SUPPORTED_REPLACE_TYPES),
        )
    except ValueError as exc:
        return {"target": None, "type_config": None, "target_error": str(exc)}
    return {
        "target": target,
        "type_config": SUPPORTED_REPLACE_TYPES[target.secret_type],
        "target_error": None,
    }


def _required(value: str | None, label: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{label} is required.")
    return normalized


def _bound_target(form: Any) -> LiveSecretSnapshot:
    selected = (
        _required(form.get("cluster_id"), "Cluster"),
        _required(form.get("namespace"), "Namespace"),
        _required(form.get("secret_name"), "Secret target"),
    )
    bound = (
        _required(form.get("target_cluster_id"), "Bound cluster"),
        _required(form.get("target_namespace"), "Bound namespace"),
        _required(form.get("target_secret_name"), "Bound Secret target"),
    )
    if selected != bound:
        raise ValueError(
            "The Secret selection changed after the live editor was loaded. Reload the target and retry."
        )
    return read_live_secret(
        *bound,
        supported_types=set(SUPPORTED_REPLACE_TYPES),
    )


def _api_error_message(exc: ApiException) -> str:
    status = getattr(exc, "status", None)
    if status == 404:
        return "The selected Secret no longer exists in Kubernetes. Reload the live target and retry."
    if status == 403:
        return "Kubernetes denied this update. Verify the cluster credential can patch Secrets in the namespace."
    if status == 401:
        return "Kubernetes authentication failed for the selected cluster."
    if status == 409:
        return "The live Secret changed after it was loaded. Reload the target before retrying the replacement."
    if status == 422:
        return "Kubernetes rejected the patch. The Secret may be immutable or the submitted data may be invalid."
    if status == 400:
        return "Kubernetes rejected the Secret patch request."
    return "Kubernetes API rejected the Secret data replacement."


def _close_api_response(response: Any) -> None:
    if response is None:
        return
    release_conn = getattr(response, "release_conn", None)
    close = getattr(response, "close", None)
    if callable(close):
        close()
    if callable(release_conn):
        release_conn()


def _patch_secret(
    *,
    target: LiveSecretSnapshot,
    string_data: dict[str, str],
    dry_run: bool,
) -> None:
    encoded_data = {
        key: base64.b64encode(value.encode("utf-8")).decode("ascii")
        for key, value in string_data.items()
    }
    body: dict[str, Any] = {
        "metadata": {"resourceVersion": target.resource_version},
        "data": encoded_data,
    }

    with legacy_tls_context(enabled=bool(target.cluster.kube_allow_weak_tls)):
        response = core_api(target.cluster).patch_namespaced_secret(
            name=target.name,
            namespace=target.namespace,
            body=body,
            dry_run="All" if dry_run else None,
            field_manager="kaori-secret-management",
            _preload_content=False,
            _request_timeout=10,
        )
        _close_api_response(response)


def execute_secret_replacement(
    form: Any,
    files: Any,
    *,
    dry_run: bool,
) -> SecretReplacementResult:
    target = _bound_target(form)
    if target.immutable:
        raise ValueError(
            "Immutable Secrets cannot be updated. Create a replacement Secret instead."
        )

    patch_data = build_replace_patch(form, files, target)
    updated_key_names = sorted(patch_data)
    if not dry_run and (form.get("confirm_replace") or "").strip().lower() != "yes":
        raise ValueError(
            "Confirm the selected-key replacement before applying changes."
        )

    try:
        _patch_secret(
            target=target,
            string_data=patch_data,
            dry_run=True,
        )
        if not dry_run:
            _patch_secret(
                target=target,
                string_data=patch_data,
                dry_run=False,
            )
    except ApiException as exc:
        raise ValueError(_api_error_message(exc)) from exc
    except ConfigException as exc:
        raise ValueError(
            "The selected cluster kubeconfig is invalid or incomplete."
        ) from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            "KAORI could not reach the Kubernetes API for the selected cluster. "
            "Check connectivity and cluster configuration."
        ) from exc
    finally:
        for key in list(patch_data):
            patch_data[key] = ""
        patch_data.clear()

    operation = "validation" if dry_run else "replacement"
    type_config = SUPPORTED_REPLACE_TYPES[target.secret_type]
    return SecretReplacementResult(
        status="success",
        title=(
            "Secret replacement validation completed"
            if dry_run
            else "Secret data replacement completed"
        ),
        message=(
            f"{target.name} is valid and ready to update in {target.cluster_name}/{target.namespace}."
            if dry_run
            else f"{target.name} was updated in {target.cluster_name}/{target.namespace}."
        ),
        detail=None,
        metadata={
            "cluster_id": target.cluster_id,
            "cluster_name": target.cluster_name,
            "namespace": target.namespace,
            "secret_name": target.name,
            "secret_type": target.secret_type,
            "secret_type_label": type_config["label"],
            "operation": operation,
            "updated_key_names": updated_key_names,
            "updated_key_count": len(updated_key_names),
            "live_target_source": True,
            "existing_values_rendered": False,
            "existing_values_persisted": False,
        },
    )
