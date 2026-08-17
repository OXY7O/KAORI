from __future__ import annotations

import json
from typing import Any

from flask import (
    Blueprint,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.kubernetes.operations.secrets.reveal_policy import (
    cluster_reveal_readiness_evidence,
    set_namespace_reveal_policy,
    update_cluster_reveal_readiness,
)
from app.models import Cluster
from app.platform_operations.kubernetes.secret_reveal.service import build_secret_reveal_settings_context
from app.platform_operations.notifications.feedback import queue_operational_feedback
from app.platform_operations.notifications.service import record_operational_activity

bp = Blueprint('secret_reveal', __name__)


def _validate_csrf() -> None:
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError as exc:
        raise ValueError('The security token is missing or expired. Refresh the page and retry.') from exc


def _settings_request_args(cluster_id: str) -> dict[str, Any]:
    settings_args: dict[str, Any] = {'cluster_id': cluster_id}
    for key in ('namespace_q', 'namespace_policy', 'page', 'per_page'):
        value = (request.form.get(key) or '').strip()
        if value:
            settings_args[key] = value
    return settings_args


def _settings_response(cluster_id: str, operation_feedback: dict[str, Any] | None = None):
    settings_args = _settings_request_args(cluster_id)
    page_url = url_for(
        'platform_operations.kubernetes.index',
        tab='secret-reveal',
        **settings_args,
    )
    if request.headers.get('HX-Request') != 'true':
        if operation_feedback is not None:
            queue_operational_feedback(operation_feedback)
        return redirect(page_url)

    context = build_secret_reveal_settings_context(
        cluster_id,
        namespace_query=settings_args.get('namespace_q'),
        namespace_policy_filter=settings_args.get('namespace_policy'),
        page=settings_args.get('page'),
        per_page=settings_args.get('per_page'),
        refresh_namespace_source=False,
    )
    context['workspace_partial'] = True
    context['posture_oob'] = True
    workspace_html = render_template(
        'platform_operations/kubernetes/secret_reveal/_cluster_workspace.html',
        **context,
    )
    feedback_html = ''
    if operation_feedback is not None:
        feedback_html = render_template(
            'components/operational_toast.html',
            **operation_feedback,
            toast_oob=True,
        )
    response = make_response(workspace_html + feedback_html)
    response.headers['HX-Push-Url'] = page_url
    response.headers['HX-Trigger'] = json.dumps({'kaori:notifications-changed': True})
    return response


def _cluster_or_error(cluster_id: str) -> Cluster:
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        raise ValueError('The selected Kubernetes cluster was not found.')
    return cluster


def _record_settings_activity(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    metadata: dict[str, object],
) -> dict[str, Any]:
    return record_operational_activity(
        user_id=current_user.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        action_url=url_for('platform_operations.kubernetes.index', tab='secret-reveal'),
        action_label='Open Kubernetes Administration',
        action_icon='server-cog',
        metadata={
            **metadata,
            'secret_value_recorded': False,
            'kubeconfig_recorded': False,
        },
        queue_feedback=False,
    )


@bp.route('/')
@permission_required('kubernetes_secrets.manage_reveal')
def index():
    redirect_args: dict[str, Any] = {'tab': 'secret-reveal'}
    for key in ('cluster_id', 'namespace_q', 'namespace_policy', 'page', 'per_page'):
        value = (request.args.get(key) or '').strip()
        if value:
            redirect_args[key] = value
    return redirect(url_for('platform_operations.kubernetes.index', **redirect_args))


@bp.route('/workspace')
@permission_required('kubernetes_secrets.manage_reveal')
def workspace():
    context = build_secret_reveal_settings_context(
        request.args.get('cluster_id'),
        namespace_query=request.args.get('namespace_q'),
        namespace_policy_filter=request.args.get('namespace_policy'),
        page=request.args.get('page'),
        per_page=request.args.get('per_page'),
        refresh_namespace_source=request.args.get('refresh_namespace') == '1',
    )
    context['workspace_partial'] = True
    context['posture_oob'] = True
    response = make_response(
        render_template(
            'platform_operations/kubernetes/secret_reveal/_cluster_workspace.html',
            **context,
        )
    )

    selected_cluster = context.get('selected_cluster')
    push_args: dict[str, Any] = {
        'namespace_q': context['namespace_filters']['query'],
        'namespace_policy': context['namespace_filters']['policy'],
        'page': context['namespace_pagination']['page'],
        'per_page': context['namespace_pagination']['per_page'],
    }
    if selected_cluster is not None:
        push_args['cluster_id'] = selected_cluster.id
    response.headers['HX-Push-Url'] = url_for(
        'platform_operations.kubernetes.index',
        tab='secret-reveal',
        **push_args,
    )
    return response


@bp.route('/cluster/<string:cluster_id>/readiness', methods=['POST'])
@permission_required('kubernetes_secrets.manage_reveal')
def update_readiness(cluster_id: str):
    operation_feedback: dict[str, Any] | None = None
    try:
        _validate_csrf()
        cluster = _cluster_or_error(cluster_id)
        previous_encryption = bool(cluster.secret_reveal_encryption_verified)
        previous_audit = bool(cluster.secret_reveal_audit_verified)
        update_cluster_reveal_readiness(
            cluster,
            encryption_verified=request.form.get('encryption_verified') == '1',
            audit_verified=request.form.get('audit_verified') == '1',
        )
        readiness = cluster_reveal_readiness_evidence(cluster)
        ready = readiness['ready']
        operation_feedback = _record_settings_activity(
            event_type='kubernetes_secret_reveal_cluster_readiness_updated',
            status='success' if ready else 'warning',
            title='Secret Reveal cluster readiness updated',
            message=(
                f'{cluster.name} is ready for namespace-level Reveal policies.'
                if ready
                else f'{cluster.name} Reveal access is suspended until both security prerequisites are verified.'
            ),
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'encryption_verified': cluster.secret_reveal_encryption_verified,
                'previous_encryption_verified': previous_encryption,
                'audit_verified': cluster.secret_reveal_audit_verified,
                'previous_audit_verified': previous_audit,
                'cluster_credential_configured': readiness['credential_configured'],
                'uses_cluster_kubeconfig': True,
            },
        )
    except ValueError as exc:
        db.session.rollback()
        operation_feedback = _record_settings_activity(
            event_type='kubernetes_secret_reveal_cluster_readiness_failed',
            status='error',
            title='Secret Reveal readiness update failed',
            message=str(exc),
            metadata={'cluster_id': cluster_id},
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Unexpected Secret Reveal readiness update failure.')
        operation_feedback = _record_settings_activity(
            event_type='kubernetes_secret_reveal_cluster_readiness_failed',
            status='error',
            title='Secret Reveal readiness update failed',
            message='KAORI could not save the cluster security readiness settings.',
            metadata={'cluster_id': cluster_id},
        )
    return _settings_response(cluster_id, operation_feedback)


@bp.route('/cluster/<string:cluster_id>/namespace-policy', methods=['POST'])
@permission_required('kubernetes_secrets.manage_reveal')
def update_namespace_policy(cluster_id: str):
    operation_feedback: dict[str, Any] | None = None
    namespace = (request.form.get('namespace') or '').strip()
    requested_policy = (request.form.get('policy') or 'disabled').strip().lower()
    try:
        _validate_csrf()
        cluster = _cluster_or_error(cluster_id)
        change = set_namespace_reveal_policy(
            cluster,
            namespace,
            requested_policy,
            actor_user_id=current_user.id,
        )
        enabled = change.policy != 'disabled'
        operation_feedback = _record_settings_activity(
            event_type='kubernetes_secret_reveal_namespace_policy_updated',
            status='success' if enabled else 'warning',
            title='Namespace Reveal policy updated',
            message=(
                f'{cluster.name} / {change.namespace} now requires {change.policy.replace("_", " ")}.'
                if enabled
                else f'Protected Secret Reveal is disabled for {cluster.name} / {change.namespace}.'
            ),
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'namespace': change.namespace,
                'policy': change.policy,
                'previous_policy': change.previous_policy,
                'uses_cluster_kubeconfig': True,
            },
        )
    except ValueError as exc:
        db.session.rollback()
        operation_feedback = _record_settings_activity(
            event_type='kubernetes_secret_reveal_namespace_policy_failed',
            status='error',
            title='Namespace Reveal policy update failed',
            message=str(exc),
            metadata={
                'cluster_id': cluster_id,
                'namespace': namespace,
                'requested_policy': requested_policy,
            },
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Unexpected Secret Reveal namespace policy failure.')
        operation_feedback = _record_settings_activity(
            event_type='kubernetes_secret_reveal_namespace_policy_failed',
            status='error',
            title='Namespace Reveal policy update failed',
            message='KAORI could not save the namespace policy because of an internal error.',
            metadata={
                'cluster_id': cluster_id,
                'namespace': namespace,
                'requested_policy': requested_policy,
            },
        )
    return _settings_response(cluster_id, operation_feedback)
