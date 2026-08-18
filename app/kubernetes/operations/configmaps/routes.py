from __future__ import annotations

from typing import Any

from flask import current_app, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.access.rbac.decorators import any_permission_required, permission_required
from app.kubernetes.operations.configmaps.receipts import issue_delete_receipt, verify_delete_receipt
from app.kubernetes.operations.configmaps.service import (
    create_configmap,
    delete_configmap,
    get_clusters,
    get_configmaps,
    get_context,
    get_impact_context,
    get_namespaces,
    get_target,
    read_configmap,
    update_configmap,
)
from app.kubernetes.operations.operation_flow import cluster_required
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import (
    create_transient_feedback,
    get_navigation_notification_context,
    record_operational_activity,
)


def _is_htmx() -> bool:
    return request.headers.get('HX-Request') == 'true'


def _csrf() -> None:
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError as exc:
        raise ValueError('The security token is missing or expired. Refresh the page and retry.') from exc


def _target_values(source: Any) -> tuple[str, str, str]:
    return (
        (source.get('cluster_id') or '').strip(),
        (source.get('namespace') or '').strip(),
        (source.get('configmap_name') or '').strip(),
    )


def _target_url(endpoint: str, source: Any) -> str:
    cluster_id, namespace, configmap_name = _target_values(source)
    return url_for(
        endpoint,
        cluster_id=cluster_id,
        namespace=namespace,
        configmap_name=configmap_name,
    )


def _feedback(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    metadata: dict[str, Any],
    action_url: str,
    detail: str | None = None,
    queue_feedback: bool = False,
) -> dict[str, Any]:
    is_validation = (
        event_type.endswith('_validated') or 'validation' in event_type or metadata.get('operation') == 'validation'
    )
    if is_validation:
        return create_transient_feedback(
            status=status,
            title=title,
            message=message,
            detail=detail,
            action_url=action_url,
            action_label='Open ConfigMap Management',
            action_icon='file-cog',
            queue_feedback=queue_feedback,
        )

    delivery_policy = (
        OperationalDeliveryPolicy.PERSISTENT
        if event_type == 'kubernetes_configmap_deleted'
        else OperationalDeliveryPolicy.DECK_ON_FAILURE
    )
    return record_operational_activity(
        user_id=int(current_user.id),
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=action_url,
        action_label='Open ConfigMap Management',
        action_icon='file-cog',
        metadata={
            **metadata,
            'feedback_delivery': 'toast',
            'operation_domain': 'kubernetes_configmaps',
        },
        queue_feedback=queue_feedback,
        delivery_policy=delivery_policy,
    )


def _feedback_context(feedback: dict[str, Any]) -> dict[str, Any]:
    return {
        'operation_feedback': {
            **feedback,
            'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
        }
    }


def _selection_context(
    cluster_id: str,
    namespace: str,
    configmap_name: str = '',
) -> dict[str, Any]:
    context = {'clusters': get_clusters()}
    namespaces: list[str] = []
    configmaps = []
    selection_error = None
    selection_error_title = None

    if cluster_id:
        try:
            namespaces = get_namespaces(cluster_id)
        except ValueError as exc:
            selection_error = str(exc)
            selection_error_title = 'Live Namespace Lookup Failed'
            namespace = ''
            configmap_name = ''
        else:
            if namespace not in namespaces:
                namespace = ''
                configmap_name = ''
            if namespace:
                try:
                    configmaps = get_configmaps(cluster_id, namespace)
                except ValueError as exc:
                    selection_error = str(exc)
                    selection_error_title = 'Live ConfigMap Lookup Failed'
                    configmap_name = ''
                else:
                    live_names = {item.name for item in configmaps}
                    if configmap_name not in live_names:
                        configmap_name = ''

    return {
        **context,
        'selected_cluster_id': cluster_id,
        'selected_namespace': namespace,
        'selected_configmap_name': configmap_name,
        'selected_namespaces': namespaces,
        'selected_configmaps': configmaps,
        'selection_error': selection_error,
        'selection_error_title': selection_error_title,
    }


def _load_selected_target(source: Any):
    cluster_id, namespace, configmap_name = _target_values(source)
    if not (cluster_id and namespace and configmap_name):
        return None
    return get_target(cluster_id, namespace, configmap_name)


def _validation_response(
    *,
    feedback: dict[str, Any],
    form_id: str,
    preview: dict[str, Any],
    delete_validation_token: str | None = None,
):
    response = make_response(
        render_template(
            'kubernetes/operations/configmaps/_operation_response.html',
            form_id=form_id,
            validation_preview=preview,
            delete_validation_token=delete_validation_token,
            **_feedback_context(feedback),
        )
    )
    if feedback.get('status') == 'success':
        response.headers['HX-Trigger'] = '{"kaori:operation-validated":{"formId":"' + form_id + '"}}'
    return response


def _redirect_after_mutation(endpoint: str):
    redirect_url = url_for(endpoint)
    if _is_htmx():
        response = make_response('', 200)
        response.headers['HX-Redirect'] = redirect_url
        return response
    return redirect(redirect_url)


def _unexpected_failure(
    *,
    operation: str,
    endpoint: str,
    metadata: dict[str, Any],
    queue_feedback: bool,
) -> dict[str, Any]:
    current_app.logger.exception('Unexpected ConfigMap %s failure.', operation)
    return _feedback(
        event_type=f'kubernetes_configmap_{operation}_failed',
        status='error',
        title='ConfigMap Operation Failed',
        message='KAORI could not complete the ConfigMap operation because of an unexpected internal error.',
        detail='Review the Activity Audit and application logs before retrying.',
        metadata={**metadata, 'operation': operation},
        action_url=url_for(endpoint),
        queue_feedback=queue_feedback,
    )


@any_permission_required(
    'kubernetes_configmaps.view',
    'kubernetes_configmaps.create',
    'kubernetes_configmaps.update',
    'kubernetes_configmaps.delete',
)
@cluster_required(
    'ConfigMap Management',
    page_title='ConfigMap Management',
    page_description='Create, update, and remove live ConfigMaps through validated, target-aware workflows with explicit preview and audit boundaries.',
)
def configmap_management_index():
    return render_template('kubernetes/operations/configmaps/index.html', **get_context())


@permission_required('kubernetes_configmaps.create')
@cluster_required('ConfigMap Management')
def configmap_namespace_options():
    namespaces: list[str] = []
    namespace_error = None
    cluster_id = request.args.get('cluster_id', '').strip()
    if cluster_id:
        try:
            namespaces = get_namespaces(cluster_id)
        except ValueError as exc:
            namespace_error = str(exc)
    return render_template(
        'kubernetes/operations/configmaps/_namespace_options.html',
        namespaces=namespaces,
        selected_namespace=request.args.get('namespace', ''),
        cluster_selected=bool(cluster_id),
        namespace_error=namespace_error,
    )


@permission_required('kubernetes_configmaps.create')
@cluster_required(
    'ConfigMap Management',
    page_title='Create Kubernetes ConfigMap',
    page_description='Define one ConfigMap, validate it against the live Kubernetes API, then create exactly the validated object.',
)
def create_configmap_page():
    if request.method == 'GET':
        return render_template('kubernetes/operations/configmaps/create.html', **get_context())

    validate_only = request.form.get('operation') != 'create'
    queue_feedback = not _is_htmx() or not validate_only
    try:
        _csrf()
        metadata = create_configmap(request.form, dry_run=validate_only)
        feedback = _feedback(
            event_type=('kubernetes_configmap_create_validated' if validate_only else 'kubernetes_configmap_created'),
            status='success',
            title=('ConfigMap Validation Passed' if validate_only else 'ConfigMap Created'),
            message=(
                'Kubernetes accepted the ConfigMap during server-side dry-run.'
                if validate_only
                else f'{metadata["configmap_name"]} was created in {metadata["namespace"]}.'
            ),
            detail=(
                f'{metadata["cluster_name"]} · {metadata["key_count"]} keys · '
                f'{"Immutable" if metadata["immutable"] else "Mutable"}'
            ),
            metadata=metadata,
            action_url=url_for('kubernetes_operations.configmap_management'),
            queue_feedback=queue_feedback,
        )
    except ValueError as exc:
        metadata = {
            'cluster_id': request.form.get('cluster_id'),
            'namespace': request.form.get('namespace'),
            'configmap_name': request.form.get('configmap_name'),
            'operation': 'validation' if validate_only else 'creation',
        }
        feedback = _feedback(
            event_type=(
                'kubernetes_configmap_create_validation_failed'
                if validate_only
                else 'kubernetes_configmap_creation_failed'
            ),
            status='error',
            title=('ConfigMap Validation Failed' if validate_only else 'ConfigMap Creation Failed'),
            message=str(exc),
            metadata=metadata,
            action_url=url_for('kubernetes_operations.create_configmap'),
            queue_feedback=not _is_htmx(),
        )
    except Exception:
        feedback = _unexpected_failure(
            operation='creation',
            endpoint='kubernetes_operations.create_configmap',
            metadata={'cluster_id': request.form.get('cluster_id')},
            queue_feedback=not _is_htmx(),
        )

    if not validate_only and feedback.get('status') == 'success':
        return _redirect_after_mutation('kubernetes_operations.create_configmap')
    if _is_htmx():
        return _validation_response(
            feedback=feedback,
            form_id='configmap-create-form',
            preview={
                'operation': 'create',
                'status': feedback.get('status'),
                'title': feedback.get('title'),
                'message': feedback.get('message'),
                'metadata': metadata if 'metadata' in locals() else {},
            },
        )
    return redirect(url_for('kubernetes_operations.create_configmap'))


@any_permission_required('kubernetes_configmaps.update', 'kubernetes_configmaps.delete')
@cluster_required('ConfigMap Management')
def configmap_workspace():
    cluster_id, namespace, configmap_name = _target_values(request.args)
    context = _selection_context(cluster_id, namespace, configmap_name)
    workspace_mode = 'delete' if request.args.get('workspace_mode') == 'delete' else 'update'
    return render_template(
        'kubernetes/operations/configmaps/_workspace_response.html',
        clusters=context['clusters'],
        namespaces=context['selected_namespaces'],
        configmaps=context['selected_configmaps'],
        selected_cluster_id=context['selected_cluster_id'],
        selected_namespace=context['selected_namespace'],
        selected_configmap_name=context['selected_configmap_name'],
        selection_error=context['selection_error'],
        selection_error_title=context['selection_error_title'],
        workspace_mode=workspace_mode,
        delete_target_url=url_for('kubernetes_operations.configmap_delete_target'),
    )


@permission_required('kubernetes_configmaps.update')
@cluster_required('ConfigMap Management')
def configmap_editor():
    try:
        target = _load_selected_target(request.args)
        if target is None:
            raise ValueError('Select a ConfigMap to load its current values.')
        live = read_configmap(target)
        impact = get_impact_context(target)
        return render_template(
            'kubernetes/operations/configmaps/_editor_response.html',
            target=target,
            live=live,
            impact=impact,
            target_error=None,
        )
    except ValueError as exc:
        return render_template(
            'kubernetes/operations/configmaps/_editor_response.html',
            target=None,
            impact=None,
            target_error=str(exc),
        )


@permission_required('kubernetes_configmaps.delete')
@cluster_required('ConfigMap Management')
def configmap_delete_target():
    try:
        target = _load_selected_target(request.args)
        if target is None:
            raise ValueError('Select a ConfigMap to review deletion impact.')
        live = read_configmap(target)
        impact = get_impact_context(target)
        return render_template(
            'kubernetes/operations/configmaps/_delete_target_response.html',
            target=target,
            live=live,
            impact=impact,
            target_error=None,
        )
    except ValueError as exc:
        return render_template(
            'kubernetes/operations/configmaps/_delete_target_response.html',
            target=None,
            impact=None,
            target_error=str(exc),
        )


@permission_required('kubernetes_configmaps.update')
@cluster_required(
    'ConfigMap Management',
    page_title='Update ConfigMap',
    page_description='Load current values, preview the effective diff, and apply one validated live update against the exact selected ConfigMap.',
)
def update_configmap_page():
    if request.method == 'POST':
        validate_only = request.form.get('operation') != 'update'
        queue_feedback = not _is_htmx() or not validate_only
        metadata: dict[str, Any] = {}
        try:
            _csrf()
            metadata = update_configmap(request.form, dry_run=validate_only)
            diff = metadata['diff']
            feedback = _feedback(
                event_type=(
                    'kubernetes_configmap_update_validated' if validate_only else 'kubernetes_configmap_updated'
                ),
                status='success',
                title=('ConfigMap Update Validated' if validate_only else 'ConfigMap Updated'),
                message=(
                    f'{len(diff["added"])} added, {len(diff["changed"])} changed, '
                    f'and {len(diff["removed"])} removed keys.'
                ),
                detail=f'{metadata["cluster_name"]} · {metadata["namespace"]} / {metadata["configmap_name"]}',
                metadata=metadata,
                action_url=_target_url('kubernetes_operations.update_configmap', request.form),
                queue_feedback=queue_feedback,
            )
        except ValueError as exc:
            metadata = {
                'cluster_id': request.form.get('cluster_id'),
                'namespace': request.form.get('namespace'),
                'configmap_name': request.form.get('configmap_name'),
                'operation': 'validation' if validate_only else 'update',
            }
            feedback = _feedback(
                event_type='kubernetes_configmap_update_failed',
                status='error',
                title=('ConfigMap Update Validation Failed' if validate_only else 'ConfigMap Update Failed'),
                message=str(exc),
                metadata=metadata,
                action_url=url_for('kubernetes_operations.update_configmap'),
                queue_feedback=not _is_htmx(),
            )
        except Exception:
            feedback = _unexpected_failure(
                operation='update',
                endpoint='kubernetes_operations.update_configmap',
                metadata={'configmap_name': request.form.get('configmap_name')},
                queue_feedback=not _is_htmx(),
            )

        if not validate_only and feedback.get('status') == 'success':
            return _redirect_after_mutation('kubernetes_operations.update_configmap')
        if _is_htmx():
            return _validation_response(
                feedback=feedback,
                form_id='configmap-update-form',
                preview={
                    'operation': 'update',
                    'status': feedback.get('status'),
                    'title': feedback.get('title'),
                    'message': feedback.get('message'),
                    'metadata': metadata,
                },
            )
        return redirect(_target_url('kubernetes_operations.update_configmap', request.form))

    cluster_id, namespace, configmap_name = _target_values(request.args)
    context = _selection_context(cluster_id, namespace, configmap_name)
    target = None
    live = None
    impact = None
    target_error = None
    if context['selected_configmap_name']:
        try:
            target = get_target(
                context['selected_cluster_id'],
                context['selected_namespace'],
                context['selected_configmap_name'],
            )
            live = read_configmap(target)
            impact = get_impact_context(target)
        except ValueError as exc:
            target_error = str(exc)

    return render_template(
        'kubernetes/operations/configmaps/update.html',
        target=target,
        live=live,
        impact=impact,
        target_error=target_error,
        **context,
    )


@permission_required('kubernetes_configmaps.delete')
@cluster_required(
    'ConfigMap Management',
    page_title='Delete ConfigMap',
    page_description='Review impact, validate the exact live target and resource version, then explicitly confirm destructive ConfigMap removal.',
)
def delete_configmap_page():
    if request.method == 'POST':
        validate_only = request.form.get('operation') != 'delete'
        metadata: dict[str, Any] = {}
        delete_validation_token: str | None = None
        try:
            _csrf()
            expected_resource_version = None
            if not validate_only:
                cluster_id, namespace, configmap_name = _target_values(request.form)
                receipt = verify_delete_receipt(
                    request.form.get('delete_validation_token') or '',
                    user_id=int(current_user.id),
                    cluster_id=cluster_id,
                    namespace=namespace,
                    configmap_name=configmap_name,
                )
                expected_resource_version = receipt.resource_version
            metadata = delete_configmap(
                request.form,
                validate_only=validate_only,
                expected_resource_version=expected_resource_version,
            )
            if validate_only:
                delete_validation_token = issue_delete_receipt(metadata, user_id=int(current_user.id))
            feedback = _feedback(
                event_type=(
                    'kubernetes_configmap_delete_validated' if validate_only else 'kubernetes_configmap_deleted'
                ),
                status='success',
                title=('ConfigMap Deletion Validated' if validate_only else 'ConfigMap Deleted'),
                message=(
                    'The exact live object and effective delete authorization were validated.'
                    if validate_only
                    else f'{metadata["configmap_name"]} was deleted from {metadata["namespace"]}.'
                ),
                detail=(
                    'The signed validation receipt is valid for ten minutes and for this user, target, and resource version.'
                    if validate_only
                    else metadata['cluster_name']
                ),
                metadata=metadata,
                action_url=url_for('kubernetes_operations.configmap_management'),
                queue_feedback=not _is_htmx() or not validate_only,
            )
        except ValueError as exc:
            metadata = {
                'cluster_id': request.form.get('cluster_id'),
                'namespace': request.form.get('namespace'),
                'configmap_name': request.form.get('configmap_name'),
                'operation': 'validation' if validate_only else 'deletion',
            }
            feedback = _feedback(
                event_type='kubernetes_configmap_delete_failed',
                status='error',
                title=('ConfigMap Deletion Validation Failed' if validate_only else 'ConfigMap Deletion Failed'),
                message=str(exc),
                metadata=metadata,
                action_url=url_for('kubernetes_operations.delete_configmap'),
                queue_feedback=not _is_htmx(),
            )
        except Exception:
            feedback = _unexpected_failure(
                operation='deletion',
                endpoint='kubernetes_operations.delete_configmap',
                metadata={'configmap_name': request.form.get('configmap_name')},
                queue_feedback=not _is_htmx(),
            )

        if not validate_only and feedback.get('status') == 'success':
            return _redirect_after_mutation('kubernetes_operations.delete_configmap')
        if _is_htmx():
            return _validation_response(
                feedback=feedback,
                form_id='configmap-delete-form',
                preview={
                    'operation': 'delete',
                    'status': feedback.get('status'),
                    'title': feedback.get('title'),
                    'message': feedback.get('message'),
                    'metadata': metadata,
                },
                delete_validation_token=delete_validation_token,
            )
        return redirect(_target_url('kubernetes_operations.delete_configmap', request.form))

    cluster_id, namespace, configmap_name = _target_values(request.args)
    context = _selection_context(cluster_id, namespace, configmap_name)
    target = None
    live = None
    impact = None
    target_error = None
    if context['selected_configmap_name']:
        try:
            target = get_target(
                context['selected_cluster_id'],
                context['selected_namespace'],
                context['selected_configmap_name'],
            )
            live = read_configmap(target)
            impact = get_impact_context(target)
        except ValueError as exc:
            target_error = str(exc)

    return render_template(
        'kubernetes/operations/configmaps/delete.html',
        target=target,
        live=live,
        impact=impact,
        target_error=target_error,
        delete_validation_token=None,
        **context,
    )
