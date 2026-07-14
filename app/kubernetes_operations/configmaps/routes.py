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
from app.notifications.service import get_navigation_notification_context, record_operational_activity
from app.rbac.decorators import any_permission_required, permission_required


def _csrf() -> None:
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError as exc:
        raise ValueError('The security token is missing or expired. Refresh the page and retry.') from exc


def _feedback(*, event_type: str, status: str, title: str, message: str, metadata: dict[str, Any], action_url: str) -> dict[str, Any]:
    return record_operational_activity(
        user_id=current_user.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        action_url=action_url,
        action_label='Open ConfigMap Management',
        action_icon='file-cog',
        metadata=metadata,
        queue_feedback=request.headers.get('HX-Request') != 'true',
    )


def _oob(feedback: dict[str, Any]) -> dict[str, Any]:
    return {
        'operation_feedback': {
            **feedback,
            'notification_context': get_navigation_notification_context(user_id=current_user.id),
        }
    }


@any_permission_required(
    'kubernetes_configmaps.view',
    'kubernetes_configmaps.create',
    'kubernetes_configmaps.update',
    'kubernetes_configmaps.delete',
)
def configmap_management_index():
    return render_template('kubernetes_operations/configmaps/index.html', **get_context())


@permission_required('kubernetes_configmaps.create')
def configmap_namespace_options():
    return render_template(
        'kubernetes_operations/configmaps/_namespace_options.html',
        namespaces=get_namespaces(request.args.get('cluster_id', '')),
        selected_namespace=request.args.get('namespace', ''),
    )


@permission_required('kubernetes_configmaps.create')
def create_configmap_page():
    result = None
    feedback = None
    if request.method == 'POST':
        dry_run = request.form.get('operation') != 'create'
        try:
            _csrf()
            if not dry_run:
                create_configmap(request.form, dry_run=True)
            metadata = create_configmap(request.form, dry_run=dry_run)
            title = 'ConfigMap validation completed' if dry_run else 'ConfigMap created'
            message = (
                'Kubernetes accepted the ConfigMap payload during server-side dry-run.'
                if dry_run else
                f'ConfigMap {metadata["configmap_name"]} was created in namespace {metadata["namespace"]}.'
            )
            feedback = _feedback(
                event_type='kubernetes_configmap_validated' if dry_run else 'kubernetes_configmap_created',
                status='success', title=title, message=message, metadata=metadata,
                action_url=url_for('kubernetes_operations.create_configmap'),
            )
            result = {'status': 'success', 'title': title, 'message': message}
        except ValueError as exc:
            title = 'ConfigMap validation failed' if dry_run else 'ConfigMap creation failed'
            metadata = {
                'cluster_id': request.form.get('cluster_id'),
                'namespace': request.form.get('namespace'),
                'configmap_name': request.form.get('configmap_name'),
                'operation': 'validation' if dry_run else 'creation',
            }
            feedback = _feedback(
                event_type='kubernetes_configmap_validation_failed' if dry_run else 'kubernetes_configmap_creation_failed',
                status='error', title=title, message=str(exc), metadata=metadata,
                action_url=url_for('kubernetes_operations.create_configmap'),
            )
            result = {'status': 'error', 'title': title, 'message': str(exc)}
        except Exception:
            current_app.logger.exception('Unexpected ConfigMap create failure.')
            title = 'ConfigMap operation failed'
            message = 'KAORI could not complete the ConfigMap operation because of an unexpected internal error.'
            feedback = _feedback(
                event_type='kubernetes_configmap_creation_failed', status='error', title=title,
                message=message, metadata={'operation': 'creation'},
                action_url=url_for('kubernetes_operations.create_configmap'),
            )
            result = {'status': 'error', 'title': title, 'message': message}
        if request.headers.get('HX-Request') == 'true':
            return render_template('kubernetes_operations/configmaps/_operation_result.html', operation_result=result, **_oob(feedback))
    return render_template('kubernetes_operations/configmaps/create.html', operation_result=result, operation_feedback=feedback, **get_context())


@any_permission_required('kubernetes_configmaps.update', 'kubernetes_configmaps.delete')
def configmap_workspace():
    cluster_id = request.args.get('cluster_id', '')
    namespace = request.args.get('namespace', '')
    return render_template(
        'kubernetes_operations/configmaps/_workspace.html',
        clusters=get_context()['clusters'],
        namespaces=get_namespaces(cluster_id),
        configmaps=get_configmaps(cluster_id, namespace),
        selected_cluster_id=cluster_id,
        selected_namespace=namespace,
        selected_inventory_id=request.args.get('inventory_id', ''),
        workspace_mode=request.args.get('workspace_mode', 'update'),
        delete_target_url=url_for('kubernetes_operations.configmap_delete_target'),
    )


@permission_required('kubernetes_configmaps.update')
def configmap_editor():
    inventory_id = int(request.args.get('inventory_id') or 0)
    target = get_target(inventory_id)
    live = read_configmap(target)
    return render_template(
        'kubernetes_operations/configmaps/_editor.html',
        target=target,
        live=live,
        impacts=get_impact_context(target),
    )


@permission_required('kubernetes_configmaps.delete')
def configmap_delete_target():
    inventory_id = int(request.args.get('inventory_id') or 0)
    target = get_target(inventory_id)
    return render_template(
        'kubernetes_operations/configmaps/_delete_target.html',
        target=target,
        impacts=get_impact_context(target),
    )


@permission_required('kubernetes_configmaps.update')
def update_configmap_page():
    result = None
    feedback = None
    selected_inventory_id = request.values.get('inventory_id', '')
    target = None
    live = None
    impacts = []
    if selected_inventory_id:
        try:
            target = get_target(int(selected_inventory_id))
            live = read_configmap(target)
            impacts = get_impact_context(target)
        except Exception:
            target = None
    if request.method == 'POST':
        dry_run = request.form.get('operation') != 'update'
        try:
            _csrf()
            if not dry_run:
                update_configmap(request.form, dry_run=True)
            metadata = update_configmap(request.form, dry_run=dry_run)
            diff = metadata['diff']
            title = 'ConfigMap update validated' if dry_run else 'ConfigMap updated'
            message = (
                f'{len(diff["added"])} added, {len(diff["changed"])} changed, and {len(diff["removed"])} removed keys.'
            )
            feedback = _feedback(
                event_type='kubernetes_configmap_update_validated' if dry_run else 'kubernetes_configmap_updated',
                status='success', title=title, message=message, metadata=metadata,
                action_url=url_for('kubernetes_operations.update_configmap', inventory_id=request.form.get('inventory_id')),
            )
            result = {'status': 'success', 'title': title, 'message': message, 'diff': diff}
        except ValueError as exc:
            title = 'ConfigMap update validation failed' if dry_run else 'ConfigMap update failed'
            feedback = _feedback(
                event_type='kubernetes_configmap_update_failed', status='error', title=title,
                message=str(exc), metadata={'inventory_id': request.form.get('inventory_id'), 'operation': 'validation' if dry_run else 'update'},
                action_url=url_for('kubernetes_operations.update_configmap'),
            )
            result = {'status': 'error', 'title': title, 'message': str(exc)}
        if request.headers.get('HX-Request') == 'true':
            return render_template('kubernetes_operations/configmaps/_operation_result.html', operation_result=result, **_oob(feedback))
    return render_template('kubernetes_operations/configmaps/update.html', operation_result=result, operation_feedback=feedback, target=target, live=live, impacts=impacts, selected_namespaces=get_namespaces(target.inventory.cluster_id) if target else [], selected_configmaps=get_configmaps(target.inventory.cluster_id, target.inventory.namespace) if target else [], **get_context())


@permission_required('kubernetes_configmaps.delete')
def delete_configmap_page():
    result = None
    feedback = None
    selected_inventory_id = request.values.get('inventory_id', '')
    target = None
    impacts = []
    if selected_inventory_id:
        try:
            target = get_target(int(selected_inventory_id))
            impacts = get_impact_context(target)
        except Exception:
            target = None
    if request.method == 'POST':
        dry_run = request.form.get('operation') != 'delete'
        try:
            _csrf()
            if not dry_run:
                delete_configmap(request.form, dry_run=True)
            metadata = delete_configmap(request.form, dry_run=dry_run)
            title = 'ConfigMap deletion validated' if dry_run else 'ConfigMap deleted'
            message = (
                'Kubernetes accepted the deletion during server-side dry-run.' if dry_run else
                f'ConfigMap {metadata["configmap_name"]} was deleted from namespace {metadata["namespace"]}.'
            )
            feedback = _feedback(
                event_type='kubernetes_configmap_delete_validated' if dry_run else 'kubernetes_configmap_deleted',
                status='success', title=title, message=message, metadata=metadata,
                action_url=url_for('kubernetes_operations.configmap_management'),
            )
            result = {'status': 'success', 'title': title, 'message': message}
            if not dry_run:
                target = None
        except ValueError as exc:
            title = 'ConfigMap deletion validation failed' if dry_run else 'ConfigMap deletion failed'
            feedback = _feedback(
                event_type='kubernetes_configmap_delete_failed', status='error', title=title,
                message=str(exc), metadata={'inventory_id': request.form.get('inventory_id'), 'operation': 'validation' if dry_run else 'delete'},
                action_url=url_for('kubernetes_operations.delete_configmap'),
            )
            result = {'status': 'error', 'title': title, 'message': str(exc)}
        if request.headers.get('HX-Request') == 'true':
            return render_template('kubernetes_operations/configmaps/_operation_result.html', operation_result=result, **_oob(feedback))
    return render_template('kubernetes_operations/configmaps/delete.html', operation_result=result, operation_feedback=feedback, target=target, impacts=impacts, selected_namespaces=get_namespaces(target.inventory.cluster_id) if target else [], selected_configmaps=get_configmaps(target.inventory.cluster_id, target.inventory.namespace) if target else [], **get_context())
