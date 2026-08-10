from __future__ import annotations

from typing import Any

from flask import (
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.kubernetes_operations.operation_flow import cluster_required, validate_then_apply
from app.kubernetes_operations.secrets.create_service import execute_secret_operation, get_secret_create_context
from app.kubernetes_operations.secrets.delete_service import (
    execute_secret_deletion,
    get_delete_target_context,
    get_delete_workspace,
    get_secret_delete_context,
)
from app.kubernetes_operations.secrets.live_service import list_live_namespaces
from app.kubernetes_operations.secrets.receipts import issue_delete_receipt, verify_delete_receipt
from app.kubernetes_operations.secrets.replace_service import (
    execute_secret_replacement,
    get_replace_target_context,
    get_replace_workspace,
    get_secret_replace_context,
)
from app.kubernetes_operations.secrets.route_support import (
    notification_response_context as _notification_response_context,
)
from app.kubernetes_operations.secrets.route_support import (
    record_secret_activity as _record_secret_activity,
)
from app.kubernetes_operations.secrets.route_support import (
    validate_secret_operation_csrf as _validate_secret_operation_csrf,
)
from app.kubernetes_operations.secrets.service import get_secret_management_overview
from app.rbac.decorators import any_permission_required, permission_required

_SAFE_SUBMITTED_FIELDS = {
    'cluster_id',
    'namespace',
    'secret_name',
    'secret_type',
    'immutable',
    'username',
    'registry_server',
    'registry_username',
    'registry_email',
}


def _safe_secret_submission(form: Any) -> dict[str, str]:
    return {key: form.get(key, '') for key in _SAFE_SUBMITTED_FIELDS if form.get(key) is not None}


def _rewind_uploaded_files(files: Any) -> None:
    """Reset uploaded streams so validation and mutation can consume the same payload."""
    for storage in files.values():
        stream = getattr(storage, 'stream', None)
        if stream is not None and hasattr(stream, 'seek'):
            stream.seek(0)


def _safe_opaque_entries(form: Any) -> list[dict[str, Any]]:
    keys = [value.strip() for value in form.getlist('generic_key')]
    normalized = [{'key': key, 'value': '', 'visible': False} for key in keys if key]
    return normalized or [{'key': '', 'value': '', 'visible': False}]


@any_permission_required(
    'kubernetes_secrets.view',
    'kubernetes_secrets.create',
    'kubernetes_secrets.replace',
    'kubernetes_secrets.delete',
    'kubernetes_secrets.reveal',
    'kubernetes_secrets.approve_reveal',
    'kubernetes_secrets.rotate_tls',
    'kubernetes_secrets.bulk_rotate_tls',
)
@cluster_required('Secret Management')
def secret_management_index():
    return render_template(
        'kubernetes_operations/secrets/index.html',
        overview=get_secret_management_overview(),
    )


@permission_required('kubernetes_secrets.create')
@cluster_required('Secret Management')
def secret_namespace_options():
    cluster_id = request.args.get('cluster_id', '')
    selected_namespace = request.args.get('namespace', '')
    namespace_error = None
    namespaces: list[str] = []
    if cluster_id.strip():
        try:
            namespaces = list_live_namespaces(cluster_id)
        except ValueError as exc:
            namespace_error = str(exc)

    return render_template(
        'kubernetes_operations/secrets/_namespace_field.html',
        namespaces=namespaces,
        selected_namespace=selected_namespace,
        cluster_selected=bool(cluster_id.strip()),
        namespace_error=namespace_error,
    )


@permission_required('kubernetes_secrets.create')
@cluster_required('Secret Management')
def create_secret():
    operation_feedback = None
    submitted = _safe_secret_submission(request.form) if request.method == 'POST' else {}
    context = get_secret_create_context()
    namespace_selection_error = None
    selected_cluster_id = submitted.get('cluster_id', '')
    if selected_cluster_id:
        try:
            context['namespace_options'][selected_cluster_id] = list_live_namespaces(selected_cluster_id)
        except ValueError as exc:
            namespace_selection_error = str(exc)
    opaque_entries = (
        _safe_opaque_entries(request.form) if request.method == 'POST' else [{'key': '', 'value': '', 'visible': False}]
    )
    is_htmx = request.headers.get('HX-Request') == 'true'

    if request.method == 'POST':
        operation = (request.form.get('operation') or 'validate').strip().lower()
        dry_run = operation != 'create'
        try:
            _validate_secret_operation_csrf()
            if operation not in {'validate', 'create'}:
                raise ValueError('Unsupported Secret action.')

            result = (
                execute_secret_operation(request.form, request.files, dry_run=True)
                if dry_run
                else validate_then_apply(
                    validate=lambda: execute_secret_operation(request.form, request.files, dry_run=True),
                    prepare_apply=lambda: _rewind_uploaded_files(request.files),
                    apply=lambda: execute_secret_operation(request.form, request.files, dry_run=False),
                )
            )
            event_type = 'kubernetes_secret_validation' if dry_run else 'kubernetes_secret_created'
            feedback = _record_secret_activity(
                event_type=event_type,
                status=result.status,
                title=result.title,
                message=result.message,
                metadata=result.metadata,
                action_url=url_for('kubernetes_operations.create_secret'),
                action_label='Open Create Secret',
                queue_feedback=(not is_htmx or not dry_run),
            )
            if not dry_run and result.status == 'success':
                redirect_url = url_for('kubernetes_operations.create_secret')
                if is_htmx:
                    response = make_response('', 200)
                    response.headers['HX-Redirect'] = redirect_url
                    return response
                return redirect(redirect_url)
        except ValueError as exc:
            title = 'Secret validation failed' if dry_run else 'Secret creation failed'
            feedback = _record_secret_activity(
                event_type=('kubernetes_secret_validation_failed' if dry_run else 'kubernetes_secret_creation_failed'),
                status='error',
                title=title,
                message=str(exc),
                metadata={
                    'cluster_id': request.form.get('cluster_id'),
                    'namespace': request.form.get('namespace'),
                    'secret_name': request.form.get('secret_name'),
                    'secret_type': request.form.get('secret_type'),
                    'operation': 'validation' if dry_run else 'creation',
                },
                action_url=url_for('kubernetes_operations.create_secret'),
                action_label='Review Secret form',
                queue_feedback=not is_htmx,
            )
        except Exception:
            current_app.logger.exception('Unexpected Kubernetes Secret operation failure.')
            title = 'Secret validation failed' if dry_run else 'Secret creation failed'
            message = 'KAORI could not complete the operation because of an unexpected internal error.'
            feedback = _record_secret_activity(
                event_type=('kubernetes_secret_validation_failed' if dry_run else 'kubernetes_secret_creation_failed'),
                status='error',
                title=title,
                message=message,
                metadata={
                    'cluster_id': request.form.get('cluster_id'),
                    'namespace': request.form.get('namespace'),
                    'secret_name': request.form.get('secret_name'),
                    'secret_type': request.form.get('secret_type'),
                    'operation': 'validation' if dry_run else 'creation',
                },
                action_url=url_for('kubernetes_operations.create_secret'),
                action_label='Review Secret form',
                queue_feedback=not is_htmx,
            )

        if is_htmx:
            operation_feedback = _notification_response_context(feedback)
            response = make_response(
                render_template(
                    'kubernetes_operations/secrets/_create_operation_result.html',
                    operation_feedback=operation_feedback,
                )
            )
            if dry_run and feedback.get('status') == 'success':
                response.headers['HX-Trigger'] = '{"kaori:operation-validated":{"formId":"secret-create-form"}}'
            return response

    return render_template(
        'kubernetes_operations/secrets/create.html',
        operation_feedback=operation_feedback,
        submitted=submitted,
        opaque_entries=opaque_entries,
        namespace_selection_error=namespace_selection_error,
        **context,
    )


def _replacement_target_metadata(target: Any | None, *, operation: str) -> dict[str, Any]:
    return {
        'cluster_id': getattr(target, 'cluster_id', None),
        'namespace': getattr(target, 'namespace', None),
        'secret_name': getattr(target, 'name', None),
        'secret_type': getattr(target, 'secret_type', None),
        'operation': operation,
        'live_target_source': True,
        'existing_values_rendered': False,
        'existing_values_persisted': False,
    }


@permission_required('kubernetes_secrets.replace')
@cluster_required('Secret Management')
def replace_secret_workspace():
    return render_template(
        'kubernetes_operations/secrets/_replace_target_workspace.html',
        **get_replace_workspace(
            request.args.get('cluster_id'),
            request.args.get('namespace'),
            request.args.get('secret_name'),
        ),
        reset_content=True,
    )


@permission_required('kubernetes_secrets.replace')
@cluster_required('Secret Management')
def replace_secret_content():
    return render_template(
        'kubernetes_operations/secrets/_replace_content_form.html',
        **get_replace_target_context(
            request.args.get('cluster_id'),
            request.args.get('namespace'),
            request.args.get('secret_name'),
        ),
    )


@permission_required('kubernetes_secrets.replace')
@cluster_required('Secret Management')
def replace_secret():
    operation_feedback = None
    is_htmx = request.headers.get('HX-Request') == 'true'
    source = request.form if request.method == 'POST' else request.args
    selected_cluster_id = source.get('cluster_id', '')
    selected_namespace = source.get('namespace', '')
    selected_secret_name = source.get('secret_name', '')
    target_context = get_replace_target_context(
        selected_cluster_id,
        selected_namespace,
        selected_secret_name,
    )
    selected_target = target_context.get('target')
    workspace_context = get_replace_workspace(
        selected_cluster_id,
        selected_namespace,
        selected_secret_name,
    )

    if request.method == 'POST':
        operation = (request.form.get('operation') or 'validate').strip().lower()
        dry_run = operation != 'replace'
        try:
            _validate_secret_operation_csrf()
            if operation not in {'validate', 'replace'}:
                raise ValueError('Unsupported Secret replacement action.')

            result = (
                execute_secret_replacement(request.form, request.files, dry_run=True)
                if dry_run
                else validate_then_apply(
                    validate=lambda: execute_secret_replacement(request.form, request.files, dry_run=True),
                    prepare_apply=lambda: _rewind_uploaded_files(request.files),
                    apply=lambda: execute_secret_replacement(request.form, request.files, dry_run=False),
                )
            )
            feedback = _record_secret_activity(
                event_type=(
                    'kubernetes_secret_replacement_validation' if dry_run else 'kubernetes_secret_data_replaced'
                ),
                status=result.status,
                title=result.title,
                message=result.message,
                metadata=result.metadata,
                action_url=url_for(
                    'kubernetes_operations.replace_secret',
                    cluster_id=result.metadata.get('cluster_id'),
                    namespace=result.metadata.get('namespace'),
                    secret_name=result.metadata.get('secret_name'),
                ),
                action_label='Open Replace Secret Data',
                queue_feedback=(not is_htmx or not dry_run),
            )
            target_context = get_replace_target_context(
                result.metadata.get('cluster_id'),
                result.metadata.get('namespace'),
                result.metadata.get('secret_name'),
            )
            if not dry_run and result.status == 'success':
                redirect_url = url_for('kubernetes_operations.replace_secret')
                if is_htmx:
                    response = make_response('', 200)
                    response.headers['HX-Redirect'] = redirect_url
                    return response
                return redirect(redirect_url)
        except ValueError as exc:
            title = 'Secret replacement validation failed' if dry_run else 'Secret data replacement failed'
            feedback = _record_secret_activity(
                event_type=(
                    'kubernetes_secret_replacement_validation_failed'
                    if dry_run
                    else 'kubernetes_secret_data_replacement_failed'
                ),
                status='error',
                title=title,
                message=str(exc),
                metadata=_replacement_target_metadata(
                    selected_target,
                    operation='validation' if dry_run else 'replacement',
                ),
                action_url=url_for('kubernetes_operations.replace_secret'),
                action_label='Review replacement form',
                queue_feedback=not is_htmx,
            )
        except Exception:
            current_app.logger.exception('Unexpected Kubernetes Secret replacement failure.')
            title = 'Secret replacement validation failed' if dry_run else 'Secret data replacement failed'
            message = 'KAORI could not complete the replacement because of an unexpected internal error.'
            feedback = _record_secret_activity(
                event_type=(
                    'kubernetes_secret_replacement_validation_failed'
                    if dry_run
                    else 'kubernetes_secret_data_replacement_failed'
                ),
                status='error',
                title=title,
                message=message,
                metadata=_replacement_target_metadata(
                    selected_target,
                    operation='validation' if dry_run else 'replacement',
                ),
                action_url=url_for('kubernetes_operations.replace_secret'),
                action_label='Review replacement form',
                queue_feedback=not is_htmx,
            )

        if is_htmx:
            operation_feedback = _notification_response_context(feedback)
            response = make_response(
                render_template(
                    'kubernetes_operations/secrets/_replace_operation_result.html',
                    operation_feedback=operation_feedback,
                )
            )
            if dry_run and feedback.get('status') == 'success':
                response.headers['HX-Trigger'] = '{"kaori:operation-validated":{"formId":"replace-secret-form"}}'
            return response

    return render_template(
        'kubernetes_operations/secrets/replace.html',
        operation_feedback=operation_feedback,
        **target_context,
        **workspace_context,
        **get_secret_replace_context(),
    )


@permission_required('kubernetes_secrets.delete')
@cluster_required('Secret Management')
def delete_secret_workspace():
    return render_template(
        'kubernetes_operations/secrets/_delete_target_workspace.html',
        **get_delete_workspace(
            request.args.get('cluster_id'),
            request.args.get('namespace'),
            request.args.get('secret_name'),
        ),
        reset_target=True,
    )


@permission_required('kubernetes_secrets.delete')
@cluster_required('Secret Management')
def delete_secret_target():
    return render_template(
        'kubernetes_operations/secrets/_delete_target.html',
        **get_delete_target_context(
            request.args.get('cluster_id'),
            request.args.get('namespace'),
            request.args.get('secret_name'),
        ),
    )


@permission_required('kubernetes_secrets.delete')
@cluster_required('Secret Management')
def delete_secret():
    operation_feedback = None
    delete_validation_token = None
    delete_completed = False
    is_htmx = request.headers.get('HX-Request') == 'true'
    source = request.form if request.method == 'POST' else request.args
    cluster_id = source.get('cluster_id', '')
    namespace = source.get('namespace', '')
    secret_name = source.get('secret_name', '')
    workspace_context = get_delete_workspace(cluster_id, namespace, secret_name)
    target_context = get_delete_target_context(cluster_id, namespace, secret_name)

    if request.method == 'POST':
        operation = (request.form.get('operation') or '').strip().lower()
        validate_only = operation == 'validate'
        try:
            _validate_secret_operation_csrf()
            if operation not in {'validate', 'delete'}:
                raise ValueError('Unsupported Secret deletion action.')

            expected_resource_version = None
            if not validate_only:
                receipt = verify_delete_receipt(
                    request.form.get('delete_validation_token') or '',
                    user_id=current_user.id,
                    cluster_id=(request.form.get('cluster_id') or '').strip(),
                    namespace=(request.form.get('namespace') or '').strip(),
                    secret_name=(request.form.get('secret_name') or '').strip(),
                )
                expected_resource_version = receipt.resource_version

            result = execute_secret_deletion(
                request.form,
                validate_only=validate_only,
                expected_resource_version=expected_resource_version,
            )
            if validate_only:
                delete_validation_token = issue_delete_receipt(
                    result.metadata,
                    user_id=current_user.id,
                )
            else:
                delete_completed = True

            feedback = _record_secret_activity(
                event_type=('kubernetes_secret_deletion_validation' if validate_only else 'kubernetes_secret_deleted'),
                status=result.status,
                title=result.title,
                message=result.message,
                metadata=result.metadata,
                action_url=(
                    url_for(
                        'kubernetes_operations.delete_secret',
                        cluster_id=result.metadata.get('cluster_id'),
                        namespace=result.metadata.get('namespace'),
                        secret_name=result.metadata.get('secret_name'),
                    )
                    if validate_only
                    else url_for('kubernetes_operations.delete_secret')
                ),
                action_label='Open Delete Secret',
                queue_feedback=(not is_htmx or not validate_only),
            )
            if delete_completed and result.status == 'success':
                redirect_url = url_for('kubernetes_operations.delete_secret')
                if is_htmx:
                    response = make_response('', 200)
                    response.headers['HX-Redirect'] = redirect_url
                    return response
                return redirect(redirect_url)
        except ValueError as exc:
            title = 'Secret deletion validation failed' if validate_only else 'Secret deletion failed'
            feedback = _record_secret_activity(
                event_type='kubernetes_secret_deletion_failed',
                status='error',
                title=title,
                message=str(exc),
                metadata={
                    'cluster_id': cluster_id,
                    'namespace': namespace,
                    'secret_name': secret_name,
                    'operation': 'validation' if validate_only else 'deletion',
                    'live_target_source': True,
                    'secret_value_recorded': False,
                },
                action_url=url_for('kubernetes_operations.delete_secret'),
                action_label='Review Delete Secret',
                queue_feedback=not is_htmx,
            )
        except Exception:
            current_app.logger.exception('Unexpected Kubernetes Secret deletion failure.')
            title = 'Secret deletion validation failed' if validate_only else 'Secret deletion failed'
            message = 'KAORI could not complete the Secret deletion because of an unexpected internal error.'
            feedback = _record_secret_activity(
                event_type='kubernetes_secret_deletion_failed',
                status='error',
                title=title,
                message=message,
                metadata={
                    'cluster_id': cluster_id,
                    'namespace': namespace,
                    'secret_name': secret_name,
                    'operation': 'validation' if validate_only else 'deletion',
                    'live_target_source': True,
                    'secret_value_recorded': False,
                },
                action_url=url_for('kubernetes_operations.delete_secret'),
                action_label='Review Delete Secret',
                queue_feedback=not is_htmx,
            )

        if is_htmx:
            operation_feedback = _notification_response_context(feedback)
            response = make_response(
                render_template(
                    'kubernetes_operations/secrets/_delete_operation_result.html',
                    operation_feedback=operation_feedback,
                    delete_validation_token=delete_validation_token,
                    delete_completed=delete_completed,
                )
            )
            if validate_only and feedback.get('status') == 'success':
                response.headers['HX-Trigger'] = '{"kaori:operation-validated":{"formId":"delete-secret-form"}}'
            return response

    return render_template(
        'kubernetes_operations/secrets/delete.html',
        operation_feedback=operation_feedback,
        delete_validation_token=delete_validation_token,
        delete_completed=delete_completed,
        **workspace_context,
        **target_context,
        **get_secret_delete_context(),
    )
