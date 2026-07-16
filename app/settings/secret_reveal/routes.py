from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.extensions import db
from app.kubernetes_operations.secrets.reveal_policy import (
    set_namespace_reveal_policy,
    update_cluster_reveal_readiness,
)
from app.models import Cluster
from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required
from app.settings.secret_reveal.service import build_secret_reveal_settings_context

bp = Blueprint("secret_reveal", __name__)


def _validate_csrf() -> None:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError as exc:
        raise ValueError(
            "The security token is missing or expired. Refresh the page and retry."
        ) from exc


def _settings_redirect(cluster_id: str):
    redirect_args: dict[str, Any] = {"cluster_id": cluster_id}
    for key in ("namespace_q", "namespace_policy", "page", "per_page"):
        value = (request.form.get(key) or "").strip()
        if value:
            redirect_args[key] = value
    return redirect(url_for("settings.secret_reveal.index", **redirect_args))


def _cluster_or_error(cluster_id: str) -> Cluster:
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        raise ValueError("The selected Kubernetes cluster was not found.")
    return cluster


def _record_settings_activity(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    metadata: dict[str, object],
) -> None:
    record_operational_activity(
        user_id=current_user.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        action_url=url_for("settings.secret_reveal.index"),
        action_label="Open Secret Reveal Settings",
        action_icon="settings",
        metadata={
            **metadata,
            "secret_value_recorded": False,
            "kubeconfig_recorded": False,
        },
        queue_feedback=True,
    )


@bp.route("/")
@permission_required("kubernetes_secrets.manage_reveal")
def index():
    context = build_secret_reveal_settings_context(
        request.args.get("cluster_id"),
        namespace_query=request.args.get("namespace_q"),
        namespace_policy_filter=request.args.get("namespace_policy"),
        page=request.args.get("page"),
        per_page=request.args.get("per_page"),
    )
    return render_template("settings/secret_reveal/index.html", **context)


@bp.route("/cluster/<string:cluster_id>/readiness", methods=["POST"])
@permission_required("kubernetes_secrets.manage_reveal")
def update_readiness(cluster_id: str):
    try:
        _validate_csrf()
        cluster = _cluster_or_error(cluster_id)
        previous_encryption = bool(cluster.secret_reveal_encryption_verified)
        previous_audit = bool(cluster.secret_reveal_audit_verified)
        update_cluster_reveal_readiness(
            cluster,
            encryption_verified=request.form.get("encryption_verified") == "1",
            audit_verified=request.form.get("audit_verified") == "1",
        )
        ready = bool(
            cluster.secret_reveal_encryption_verified
            and cluster.secret_reveal_audit_verified
        )
        _record_settings_activity(
            event_type="kubernetes_secret_reveal_cluster_readiness_updated",
            status="success" if ready else "warning",
            title="Secret Reveal cluster readiness updated",
            message=(
                f"{cluster.name} is ready for namespace-level Reveal policies."
                if ready
                else f"{cluster.name} Reveal access is suspended until both security prerequisites are verified."
            ),
            metadata={
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "encryption_verified": cluster.secret_reveal_encryption_verified,
                "previous_encryption_verified": previous_encryption,
                "audit_verified": cluster.secret_reveal_audit_verified,
                "previous_audit_verified": previous_audit,
                "uses_cluster_kubeconfig": True,
            },
        )
    except ValueError as exc:
        db.session.rollback()
        _record_settings_activity(
            event_type="kubernetes_secret_reveal_cluster_readiness_failed",
            status="error",
            title="Secret Reveal readiness update failed",
            message=str(exc),
            metadata={"cluster_id": cluster_id},
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unexpected Secret Reveal readiness update failure."
        )
        _record_settings_activity(
            event_type="kubernetes_secret_reveal_cluster_readiness_failed",
            status="error",
            title="Secret Reveal readiness update failed",
            message="KAORI could not save the cluster security readiness settings.",
            metadata={"cluster_id": cluster_id},
        )
    return _settings_redirect(cluster_id)


@bp.route("/cluster/<string:cluster_id>/namespace-policy", methods=["POST"])
@permission_required("kubernetes_secrets.manage_reveal")
def update_namespace_policy(cluster_id: str):
    namespace = (request.form.get("namespace") or "").strip()
    requested_policy = (request.form.get("policy") or "disabled").strip().lower()
    try:
        _validate_csrf()
        cluster = _cluster_or_error(cluster_id)
        change = set_namespace_reveal_policy(
            cluster,
            namespace,
            requested_policy,
            actor_user_id=current_user.id,
        )
        enabled = change.policy != "disabled"
        _record_settings_activity(
            event_type="kubernetes_secret_reveal_namespace_policy_updated",
            status="success" if enabled else "warning",
            title="Namespace Reveal policy updated",
            message=(
                f"{cluster.name} / {change.namespace} now requires {change.policy.replace('_', ' ')}."
                if enabled
                else f"Protected Secret Reveal is disabled for {cluster.name} / {change.namespace}."
            ),
            metadata={
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "namespace": change.namespace,
                "policy": change.policy,
                "previous_policy": change.previous_policy,
                "uses_cluster_kubeconfig": True,
            },
        )
    except ValueError as exc:
        db.session.rollback()
        _record_settings_activity(
            event_type="kubernetes_secret_reveal_namespace_policy_failed",
            status="error",
            title="Namespace Reveal policy update failed",
            message=str(exc),
            metadata={
                "cluster_id": cluster_id,
                "namespace": namespace,
                "requested_policy": requested_policy,
            },
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unexpected Secret Reveal namespace policy failure."
        )
        _record_settings_activity(
            event_type="kubernetes_secret_reveal_namespace_policy_failed",
            status="error",
            title="Namespace Reveal policy update failed",
            message="KAORI could not save the namespace policy because of an internal error.",
            metadata={
                "cluster_id": cluster_id,
                "namespace": namespace,
                "requested_policy": requested_policy,
            },
        )
    return _settings_redirect(cluster_id)
