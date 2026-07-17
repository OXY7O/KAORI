from __future__ import annotations

from typing import Any

from flask import current_app, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.kubernetes_operations.configmaps.service import (
    create_configmap,
    delete_configmap,
    get_configmaps,
    get_context,
    get_impact_context,
    get_namespaces,
    get_target,
    read_configmap,
    update_configmap,
)
from app.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.rbac.decorators import any_permission_required, permission_required


def _csrf() -> None:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as exc:
        raise ValueError(
            "The security token is missing or expired. Refresh the page and retry."
        ) from exc


def _feedback(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    metadata: dict[str, Any],
    action_url: str,
) -> dict[str, Any]:
    return record_operational_activity(
        user_id=current_user.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        action_url=action_url,
        action_label="Open ConfigMap Management",
        action_icon="file-cog",
        metadata=metadata,
        queue_feedback=request.headers.get("HX-Request") != "true",
    )


def _oob(feedback: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation_feedback": {
            **feedback,
            "notification_context": get_navigation_notification_context(
                user_id=current_user.id
            ),
        }
    }


def _target_values(source: Any) -> tuple[str, str, str]:
    return (
        (source.get("cluster_id") or "").strip(),
        (source.get("namespace") or "").strip(),
        (source.get("configmap_name") or "").strip(),
    )


def _target_url(endpoint: str, source: Any) -> str:
    cluster_id, namespace, configmap_name = _target_values(source)
    return url_for(
        endpoint,
        cluster_id=cluster_id,
        namespace=namespace,
        configmap_name=configmap_name,
    )


def _selection_context(
    cluster_id: str,
    namespace: str,
    configmap_name: str = "",
) -> dict[str, Any]:
    context = get_context()
    namespaces: list[str] = []
    configmaps = []
    selection_error = None
    selection_error_title = None

    if cluster_id:
        try:
            namespaces = get_namespaces(cluster_id)
        except ValueError as exc:
            selection_error = str(exc)
            selection_error_title = "Live namespace lookup failed"
            namespace = ""
            configmap_name = ""
        else:
            if namespace not in namespaces:
                namespace = ""
                configmap_name = ""
            if namespace:
                try:
                    configmaps = get_configmaps(cluster_id, namespace)
                except ValueError as exc:
                    selection_error = str(exc)
                    selection_error_title = "Live ConfigMap lookup failed"
                    configmap_name = ""
                else:
                    live_names = {item.name for item in configmaps}
                    if configmap_name not in live_names:
                        configmap_name = ""

    return {
        **context,
        "selected_cluster_id": cluster_id,
        "selected_namespace": namespace,
        "selected_configmap_name": configmap_name,
        "selected_namespaces": namespaces,
        "selected_configmaps": configmaps,
        "selection_error": selection_error,
        "selection_error_title": selection_error_title,
    }


def _load_selected_target(source: Any):
    cluster_id, namespace, configmap_name = _target_values(source)
    if not (cluster_id and namespace and configmap_name):
        return None
    return get_target(cluster_id, namespace, configmap_name)


@any_permission_required(
    "kubernetes_configmaps.view",
    "kubernetes_configmaps.create",
    "kubernetes_configmaps.update",
    "kubernetes_configmaps.delete",
)
def configmap_management_index():
    return render_template(
        "kubernetes_operations/configmaps/index.html",
        **get_context(),
    )


@permission_required("kubernetes_configmaps.create")
def configmap_namespace_options():
    namespaces: list[str] = []
    namespace_error = None
    cluster_id = request.args.get("cluster_id", "")
    if cluster_id.strip():
        try:
            namespaces = get_namespaces(cluster_id)
        except ValueError as exc:
            namespace_error = str(exc)
    return render_template(
        "kubernetes_operations/configmaps/_namespace_options.html",
        namespaces=namespaces,
        selected_namespace=request.args.get("namespace", ""),
        cluster_selected=bool(cluster_id.strip()),
        namespace_error=namespace_error,
    )


@permission_required("kubernetes_configmaps.create")
def create_configmap_page():
    feedback = None
    if request.method == "POST":
        dry_run = request.form.get("operation") != "create"
        try:
            _csrf()
            metadata = create_configmap(request.form, dry_run=dry_run)
            title = "ConfigMap validation completed" if dry_run else "ConfigMap created"
            message = (
                "Kubernetes accepted the ConfigMap payload during server-side dry-run."
                if dry_run
                else f"ConfigMap {metadata['configmap_name']} was created in namespace {metadata['namespace']}."
            )
            feedback = _feedback(
                event_type=(
                    "kubernetes_configmap_validated"
                    if dry_run
                    else "kubernetes_configmap_created"
                ),
                status="success",
                title=title,
                message=message,
                metadata=metadata,
                action_url=url_for("kubernetes_operations.configmap_management"),
            )
        except ValueError as exc:
            title = (
                "ConfigMap validation failed"
                if dry_run
                else "ConfigMap creation failed"
            )
            metadata = {
                "cluster_id": request.form.get("cluster_id"),
                "namespace": request.form.get("namespace"),
                "configmap_name": request.form.get("configmap_name"),
                "operation": "validation" if dry_run else "creation",
            }
            feedback = _feedback(
                event_type=(
                    "kubernetes_configmap_validation_failed"
                    if dry_run
                    else "kubernetes_configmap_creation_failed"
                ),
                status="error",
                title=title,
                message=str(exc),
                metadata=metadata,
                action_url=url_for("kubernetes_operations.create_configmap"),
            )
        except Exception:
            current_app.logger.exception("Unexpected ConfigMap create failure.")
            feedback = _feedback(
                event_type="kubernetes_configmap_creation_failed",
                status="error",
                title="ConfigMap operation failed",
                message=(
                    "KAORI could not complete the ConfigMap operation because "
                    "of an unexpected internal error."
                ),
                metadata={"operation": "creation"},
                action_url=url_for("kubernetes_operations.create_configmap"),
            )
        if request.headers.get("HX-Request") == "true":
            return render_template(
                "kubernetes_operations/configmaps/_operation_notification.html",
                **_oob(feedback),
            )
        return redirect(url_for("kubernetes_operations.create_configmap"))
    return render_template(
        "kubernetes_operations/configmaps/create.html",
        **get_context(),
    )


@any_permission_required(
    "kubernetes_configmaps.update",
    "kubernetes_configmaps.delete",
)
def configmap_workspace():
    cluster_id, namespace, configmap_name = _target_values(request.args)
    context = _selection_context(cluster_id, namespace, configmap_name)
    return render_template(
        "kubernetes_operations/configmaps/_workspace_response.html",
        clusters=context["clusters"],
        namespaces=context["selected_namespaces"],
        configmaps=context["selected_configmaps"],
        selected_cluster_id=context["selected_cluster_id"],
        selected_namespace=context["selected_namespace"],
        selected_configmap_name=context["selected_configmap_name"],
        selection_error=context["selection_error"],
        selection_error_title=context["selection_error_title"],
        workspace_mode=request.args.get("workspace_mode", "update"),
        delete_target_url=url_for("kubernetes_operations.configmap_delete_target"),
    )


@permission_required("kubernetes_configmaps.update")
def configmap_editor():
    try:
        target = _load_selected_target(request.args)
        if target is None:
            raise ValueError("Select a ConfigMap to load its current values.")
        live = read_configmap(target)
        return render_template(
            "kubernetes_operations/configmaps/_editor.html",
            target=target,
            live=live,
            impacts=get_impact_context(target),
            target_error=None,
        )
    except ValueError as exc:
        return render_template(
            "kubernetes_operations/configmaps/_editor.html",
            target=None,
            target_error=str(exc),
        )


@permission_required("kubernetes_configmaps.delete")
def configmap_delete_target():
    try:
        target = _load_selected_target(request.args)
        if target is None:
            raise ValueError("Select a ConfigMap to review deletion impact.")
        live = read_configmap(target)
        return render_template(
            "kubernetes_operations/configmaps/_delete_target.html",
            target=target,
            live=live,
            impacts=get_impact_context(target),
            target_error=None,
        )
    except ValueError as exc:
        return render_template(
            "kubernetes_operations/configmaps/_delete_target.html",
            target=None,
            target_error=str(exc),
        )


@permission_required("kubernetes_configmaps.update")
def update_configmap_page():
    if request.method == "POST":
        dry_run = request.form.get("operation") != "update"
        try:
            _csrf()
            metadata = update_configmap(request.form, dry_run=dry_run)
            diff = metadata["diff"]
            feedback = _feedback(
                event_type=(
                    "kubernetes_configmap_update_validated"
                    if dry_run
                    else "kubernetes_configmap_updated"
                ),
                status="success",
                title=(
                    "ConfigMap update validated" if dry_run else "ConfigMap updated"
                ),
                message=(
                    f"{len(diff['added'])} added, "
                    f"{len(diff['changed'])} changed, and "
                    f"{len(diff['removed'])} removed keys."
                ),
                metadata=metadata,
                action_url=_target_url(
                    "kubernetes_operations.update_configmap",
                    request.form,
                ),
            )
        except ValueError as exc:
            feedback = _feedback(
                event_type="kubernetes_configmap_update_failed",
                status="error",
                title=(
                    "ConfigMap update validation failed"
                    if dry_run
                    else "ConfigMap update failed"
                ),
                message=str(exc),
                metadata={
                    "cluster_id": request.form.get("cluster_id"),
                    "namespace": request.form.get("namespace"),
                    "configmap_name": request.form.get("configmap_name"),
                    "operation": "validation" if dry_run else "update",
                },
                action_url=url_for("kubernetes_operations.update_configmap"),
            )
        if request.headers.get("HX-Request") == "true":
            return render_template(
                "kubernetes_operations/configmaps/_operation_notification.html",
                **_oob(feedback),
            )
        return redirect(
            _target_url(
                "kubernetes_operations.update_configmap",
                request.form,
            )
        )

    cluster_id, namespace, configmap_name = _target_values(request.args)
    context = _selection_context(cluster_id, namespace, configmap_name)
    target = None
    live = None
    impacts = []
    target_error = None
    if context["selected_configmap_name"]:
        try:
            target = get_target(
                context["selected_cluster_id"],
                context["selected_namespace"],
                context["selected_configmap_name"],
            )
            live = read_configmap(target)
            impacts = get_impact_context(target)
        except ValueError as exc:
            target_error = str(exc)

    return render_template(
        "kubernetes_operations/configmaps/update.html",
        target=target,
        live=live,
        impacts=impacts,
        target_error=target_error,
        **context,
    )


@permission_required("kubernetes_configmaps.delete")
def delete_configmap_page():
    if request.method == "POST":
        dry_run = request.form.get("operation") != "delete"
        try:
            _csrf()
            metadata = delete_configmap(request.form, dry_run=dry_run)
            feedback = _feedback(
                event_type=(
                    "kubernetes_configmap_delete_validated"
                    if dry_run
                    else "kubernetes_configmap_deleted"
                ),
                status="success",
                title=(
                    "ConfigMap deletion validated" if dry_run else "ConfigMap deleted"
                ),
                message=(
                    "Kubernetes accepted the deletion during server-side dry-run."
                    if dry_run
                    else f"ConfigMap {metadata['configmap_name']} was deleted from namespace {metadata['namespace']}."
                ),
                metadata=metadata,
                action_url=url_for("kubernetes_operations.configmap_management"),
            )
        except ValueError as exc:
            feedback = _feedback(
                event_type="kubernetes_configmap_delete_failed",
                status="error",
                title=(
                    "ConfigMap deletion validation failed"
                    if dry_run
                    else "ConfigMap deletion failed"
                ),
                message=str(exc),
                metadata={
                    "cluster_id": request.form.get("cluster_id"),
                    "namespace": request.form.get("namespace"),
                    "configmap_name": request.form.get("configmap_name"),
                    "operation": "validation" if dry_run else "delete",
                },
                action_url=url_for("kubernetes_operations.delete_configmap"),
            )
        if request.headers.get("HX-Request") == "true":
            return render_template(
                "kubernetes_operations/configmaps/_operation_notification.html",
                **_oob(feedback),
            )
        return redirect(
            url_for("kubernetes_operations.delete_configmap")
            if not dry_run
            else _target_url(
                "kubernetes_operations.delete_configmap",
                request.form,
            )
        )

    cluster_id, namespace, configmap_name = _target_values(request.args)
    context = _selection_context(cluster_id, namespace, configmap_name)
    target = None
    live = None
    impacts = []
    target_error = None
    if context["selected_configmap_name"]:
        try:
            target = get_target(
                context["selected_cluster_id"],
                context["selected_namespace"],
                context["selected_configmap_name"],
            )
            live = read_configmap(target)
            impacts = get_impact_context(target)
        except ValueError as exc:
            target_error = str(exc)

    return render_template(
        "kubernetes_operations/configmaps/delete.html",
        target=target,
        live=live,
        impacts=impacts,
        target_error=target_error,
        **context,
    )
