from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import current_app, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from wtforms.validators import ValidationError

from app.cluster.onboarding import has_registered_clusters
from app.extensions.db import db
from app.extensions.limiter import limiter
from app.kubernetes_operations.secrets.create_service import (
    execute_secret_operation,
    get_cluster_namespace_options,
    get_secret_create_context,
)
from app.kubernetes_operations.secrets.delete_service import (
    execute_secret_deletion,
    get_delete_target_context,
    get_delete_workspace,
    get_secret_delete_context,
)
from app.kubernetes_operations.secrets.replace_service import (
    execute_secret_replacement,
    get_replace_target_context,
    get_replace_workspace,
    get_secret_replace_context,
)
from app.kubernetes_operations.secrets.reveal_service import (
    ActiveRevealRequestExists,
    create_reveal_request,
    decide_reveal_request,
    get_reveal_page_context,
    get_reveal_request_for_user,
    get_reveal_target_context,
    get_reveal_workspace,
)
from app.kubernetes_operations.secrets.reveal_service import reveal_secret_value as execute_secret_value_reveal
from app.kubernetes_operations.secrets.service import (
    apply_bulk_update,
    apply_certificate_update,
    get_secret_management_overview,
    get_tls_certificate_detail,
    get_tls_certificate_page,
    preview_uploaded_pair,
)
from app.models.user import User
from app.kubernetes_operations.operation_flow import validate_then_apply
from app.notifications.service import (
    create_notification,
    get_navigation_notification_context,
    record_operational_activity,
)
from app.rbac.decorators import any_permission_required, permission_required


def _parse_certificate_ids(values: list[str]) -> list[int]:
    normalized_values = (value.strip() for value in values)
    return [int(value) for value in normalized_values if value.isdigit()]


def _notification_response_context(feedback: dict[str, Any]) -> dict[str, Any]:
    return {
        **feedback,
        'notification_context': get_navigation_notification_context(
            user_id=current_user.id,
        ),
    }


def _build_tls_rotation_preview_response(rendered_html: str, payload: dict[str, Any]):
    response = make_response(rendered_html)
    validation = payload.get('validation')
    if (
        validation is not None
        and validation.is_valid
        and validation.parsed_certificate is not None
    ):
        response.headers['HX-Trigger'] = (
            '{"kaori:operation-validated":{"formId":"tls-secret-rotate-form"}}'
        )
    return response


def _record_secret_activity(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'Open Secret Management',
    metadata: dict[str, Any] | None = None,
    queue_feedback: bool = False,
) -> dict[str, Any]:
    return record_operational_activity(
        user_id=current_user.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=action_url or url_for('kubernetes_operations.secret_management'),
        action_label=action_label,
        action_icon='key',
        metadata=metadata,
        queue_feedback=queue_feedback,
    )


def _validate_secret_operation_csrf() -> None:
    """Validate CSRF for hand-written Secret operation forms.

    Most existing KAORI forms use FlaskForm validation. Delete and Protected
    Secret Reveal use small hand-written forms, so these routes validate the
    generated token explicitly.
    """

    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError as exc:
        raise ValueError('The security token is missing or expired. Refresh the page and retry.') from exc


_SECRET_DELETE_RECEIPT_SESSION_KEY = 'secret_delete_validation_receipt'
_SECRET_DELETE_RECEIPT_MAX_AGE_SECONDS = 600


def _secret_delete_receipt_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config['SECRET_KEY'],
        salt='kaori-secret-delete-validation',
    )


def _secret_delete_target_values(source: Any) -> tuple[str, str, str]:
    return (
        (source.get('cluster_id') or '').strip(),
        (source.get('namespace') or '').strip(),
        (source.get('secret_name') or '').strip(),
    )


def _issue_secret_delete_receipt(metadata: dict[str, Any]) -> str:
    token = _secret_delete_receipt_serializer().dumps(
        {
            'cluster_id': str(metadata['cluster_id']),
            'namespace': metadata['namespace'],
            'secret_name': metadata['secret_name'],
            'resource_version': metadata['resource_version'],
        }
    )
    session[_SECRET_DELETE_RECEIPT_SESSION_KEY] = token
    return token


def _verify_secret_delete_receipt(source: Any) -> dict[str, str]:
    token = (source.get('delete_validation_token') or '').strip()
    if not token:
        raise ValueError(
            'Validate the Secret deletion before applying the final delete action.'
        )
    session_token = session.get(_SECRET_DELETE_RECEIPT_SESSION_KEY)
    if not session_token or token != session_token:
        raise ValueError(
            'The Secret deletion validation is no longer active. Run validation again.'
        )
    try:
        payload = _secret_delete_receipt_serializer().loads(
            token,
            max_age=_SECRET_DELETE_RECEIPT_MAX_AGE_SECONDS,
        )
    except SignatureExpired as exc:
        raise ValueError(
            'The deletion validation expired. Run validation again before deleting.'
        ) from exc
    except BadSignature as exc:
        raise ValueError(
            'The deletion validation receipt is invalid. Run validation again.'
        ) from exc

    expected = (
        str(payload.get('cluster_id') or ''),
        payload.get('namespace') or '',
        payload.get('secret_name') or '',
    )
    if _secret_delete_target_values(source) != expected:
        raise ValueError(
            'The selected Secret changed after validation. Run validation again.'
        )
    return {'resource_version': str(payload.get('resource_version') or '')}


def _record_validation_activity(
    *,
    preview: dict[str, Any],
    selected_ids: list[int],
    record: Any | None = None,
) -> dict[str, Any]:
    validation = preview['validation']
    target_previews = preview.get('targets') or []
    uncovered_hosts = sorted(
        {host for target_preview in target_previews for host in (target_preview.get('uncovered_hosts') or [])}
    )
    target_count = len(selected_ids)
    is_valid = bool(validation.is_valid and validation.parsed_certificate)

    if target_count == 0:
        status = 'warning'
        title = 'TLS certificate validation requires a target'
        message = 'Select at least one Kubernetes TLS Secret before validating the certificate pair.'
        detail = None
    elif not is_valid:
        status = 'error'
        title = 'TLS certificate validation failed'
        message = 'The uploaded certificate and private key could not be validated.'
        detail = ' '.join(validation.errors) if validation.errors else None
    elif uncovered_hosts:
        status = 'warning'
        title = 'TLS certificate validation completed with warnings'
        message = (
            f'The certificate pair is valid, but {len(uncovered_hosts)} mapped host'
            f'{"s are" if len(uncovered_hosts) != 1 else " is"} not covered by its SANs.'
        )
        detail = ', '.join(uncovered_hosts)
    else:
        status = 'success'
        title = 'TLS certificate validation completed'
        message = (
            f'The uploaded certificate pair is valid for {target_count} selected TLS Secret'
            f'{"s" if target_count != 1 else ""}.'
        )
        detail = None

    parsed = validation.parsed_certificate
    cluster = getattr(record, 'cluster', None) if record is not None else None
    return _record_secret_activity(
        event_type='kubernetes_tls_secret_validation',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=(
            url_for('kubernetes_operations.tls_secret_rotate', certificate_id=record.id)
            if record is not None
            else url_for('kubernetes_operations.tls_secret_bulk_rotation')
        ),
        action_label='Review TLS rotation',
        metadata={
            'certificate_id': getattr(record, 'id', None),
            'cluster_id': getattr(record, 'cluster_id', None),
            'cluster_name': getattr(cluster, 'name', None),
            'namespace': getattr(record, 'namespace', None),
            'secret_name': getattr(record, 'secret_name', None),
            'target_count': target_count,
            'validation_result': status,
            'uncovered_host_count': len(uncovered_hosts),
            'new_common_name': getattr(parsed, 'common_name', None),
            'new_expiry': (
                parsed.not_after.isoformat() if parsed is not None and parsed.not_after is not None else None
            ),
        },
    )


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
def secret_management_index():
    return render_template(
        'kubernetes_operations/secrets/index.html',
        overview=get_secret_management_overview(),
    )


@permission_required('kubernetes_secrets.create')
def secret_namespace_options():
    cluster_id = request.args.get('cluster_id', '')
    selected_namespace = request.args.get('namespace', '')
    namespace_error = None
    namespaces: list[str] = []
    if cluster_id.strip():
        try:
            namespaces = get_cluster_namespace_options(cluster_id)
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
def create_secret():
    operation_feedback = None
    submitted = _safe_secret_submission(request.form) if request.method == 'POST' else {}
    context = get_secret_create_context()
    namespace_selection_error = None
    selected_cluster_id = submitted.get('cluster_id', '')
    if selected_cluster_id:
        try:
            context['namespace_options'][selected_cluster_id] = get_cluster_namespace_options(selected_cluster_id)
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
            response = make_response(render_template(
                'kubernetes_operations/secrets/_create_operation_result.html',
                operation_feedback=operation_feedback,
            ))
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
            response = make_response(render_template(
                'kubernetes_operations/secrets/_replace_operation_result.html',
                operation_feedback=operation_feedback,
            ))
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
                receipt = _verify_secret_delete_receipt(request.form)
                expected_resource_version = receipt['resource_version']
                # Consume the receipt before mutation so it cannot be replayed.
                session.pop(_SECRET_DELETE_RECEIPT_SESSION_KEY, None)

            result = execute_secret_deletion(
                request.form,
                validate_only=validate_only,
                expected_resource_version=expected_resource_version,
            )
            if validate_only:
                delete_validation_token = _issue_secret_delete_receipt(
                    result.metadata
                )
            else:
                delete_completed = True

            feedback = _record_secret_activity(
                event_type=(
                    'kubernetes_secret_deletion_validation'
                    if validate_only
                    else 'kubernetes_secret_deleted'
                ),
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
            session.pop(_SECRET_DELETE_RECEIPT_SESSION_KEY, None)
            title = (
                'Secret deletion validation failed'
                if validate_only
                else 'Secret deletion failed'
            )
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
            session.pop(_SECRET_DELETE_RECEIPT_SESSION_KEY, None)
            current_app.logger.exception(
                'Unexpected Kubernetes Secret deletion failure.'
            )
            title = (
                'Secret deletion validation failed'
                if validate_only
                else 'Secret deletion failed'
            )
            message = (
                'KAORI could not complete the Secret deletion because of an '
                'unexpected internal error.'
            )
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
                response.headers['HX-Trigger'] = (
                    '{"kaori:operation-validated":{"formId":"delete-secret-form"}}'
                )
            return response
    else:
        session_token = session.get(_SECRET_DELETE_RECEIPT_SESSION_KEY)
        if session_token:
            try:
                _verify_secret_delete_receipt(
                    {
                        'delete_validation_token': session_token,
                        'cluster_id': cluster_id,
                        'namespace': namespace,
                        'secret_name': secret_name,
                    }
                )
            except ValueError:
                session.pop(_SECRET_DELETE_RECEIPT_SESSION_KEY, None)
            else:
                delete_validation_token = session_token

    return render_template(
        'kubernetes_operations/secrets/delete.html',
        operation_feedback=operation_feedback,
        delete_validation_token=delete_validation_token,
        delete_completed=delete_completed,
        **workspace_context,
        **target_context,
        **get_secret_delete_context(),
    )


_SECRET_REVEAL_STEP_UP_SESSION_KEY = 'kubernetes_secret_reveal_step_up'


def _client_ip() -> str | None:
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip() or None
    return request.remote_addr


def _secret_reveal_step_up_active() -> bool:
    payload = session.get(_SECRET_REVEAL_STEP_UP_SESSION_KEY)
    if not isinstance(payload, dict):
        return False
    if str(payload.get('user_id')) != str(current_user.id):
        return False
    authenticated_at_raw = payload.get('authenticated_at')
    if not isinstance(authenticated_at_raw, str):
        return False
    try:
        authenticated_at = datetime.fromisoformat(authenticated_at_raw)
    except ValueError:
        return False
    if authenticated_at.tzinfo is None:
        authenticated_at = authenticated_at.replace(tzinfo=UTC)
    ttl_seconds = int(current_app.config.get('KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS', 300))
    return (datetime.now(UTC) - authenticated_at).total_seconds() <= ttl_seconds


def _mark_secret_reveal_step_up() -> None:
    session[_SECRET_REVEAL_STEP_UP_SESSION_KEY] = {
        'user_id': current_user.id,
        'authenticated_at': datetime.now(UTC).isoformat(),
    }
    session.modified = True


def _reveal_status_context() -> dict[str, Any]:
    can_approve = current_user.has_permission('kubernetes_secrets.approve_reveal')
    return {
        **get_reveal_page_context(
            user_id=current_user.id,
            can_approve=can_approve,
            my_page=request.args.get('my_page', 1, type=int) or 1,
            my_per_page=request.args.get('my_per_page', 5, type=int) or 5,
            pending_page=request.args.get('pending_page', 1, type=int) or 1,
            pending_per_page=request.args.get('pending_per_page', 5, type=int) or 5,
        ),
        'step_up_active': _secret_reveal_step_up_active(),
        'can_reveal': current_user.has_permission('kubernetes_secrets.reveal'),
        'can_approve': can_approve,
        'notification_context': get_navigation_notification_context(
            user_id=current_user.id,
        ),
    }


def _notify_secret_reveal_approvers(record: Any) -> None:
    if getattr(record, 'status', None) != 'pending':
        return

    approvers = User.query.filter(
        User.account_is_active.is_(True),
        User.deleted_at.is_(None),
        User.id != record.requester_user_id,
    ).all()

    action_url = url_for(
        'kubernetes_operations.reveal_secret',
        _anchor='pending-secret-reveal-approvals',
    )
    metadata = _reveal_request_metadata(record)
    for approver in approvers:
        if not approver.has_permission('kubernetes_secrets.approve_reveal'):
            continue
        try:
            create_notification(
                user_id=approver.id,
                event_type='kubernetes_secret_reveal_approval_required',
                status='warning',
                title='Secret reveal approval required',
                message=(
                    f'{record.requester.display_label} requested access to '
                    f'{record.secret_name} / {record.key_name} in '
                    f'{record.cluster.name} / {record.namespace}.'
                ),
                action_url=action_url,
                metadata=metadata,
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                'Could not notify Secret reveal approver user %s for request %s.',
                approver.id,
                record.id,
            )


def _reveal_request_metadata(record: Any) -> dict[str, Any]:
    cluster = getattr(record, 'cluster', None)
    return {
        'reveal_request_id': getattr(record, 'id', None),
        'configuration_inventory_id': getattr(record, 'configuration_inventory_id', None),
        'cluster_id': getattr(record, 'cluster_id', None),
        'cluster_name': getattr(cluster, 'name', None),
        'namespace': getattr(record, 'namespace', None),
        'secret_name': getattr(record, 'secret_name', None),
        'secret_type': getattr(record, 'secret_type', None),
        'key_name': getattr(record, 'key_name', None),
        'policy': getattr(record, 'policy', None),
        'ticket_reference': getattr(record, 'ticket_reference', None),
        'reason': getattr(record, 'reason', None),
        'requester_user_id': getattr(record, 'requester_user_id', None),
        'approver_user_id': getattr(record, 'approver_user_id', None),
        'request_status': getattr(record, 'status', None),
        'secret_value_recorded': False,
        'secret_value_hash_recorded': False,
    }


@any_permission_required('kubernetes_secrets.reveal', 'kubernetes_secrets.approve_reveal')
def reveal_secret_page():
    selected_cluster_id = request.args.get('cluster_id', '')
    selected_namespace = request.args.get('namespace', '')
    selected_secret_name = request.args.get('secret_name', '')
    target_context = get_reveal_target_context(
        selected_cluster_id,
        selected_namespace,
        selected_secret_name,
    )
    workspace_context = get_reveal_workspace(
        selected_cluster_id,
        selected_namespace,
        selected_secret_name,
    )
    selected_cluster = target_context.get('selected_cluster') or workspace_context.get('selected_cluster')
    selected_namespace_policy = (
        target_context.get('selected_namespace_policy')
        if target_context.get('target') is not None
        else workspace_context.get('selected_namespace_policy', 'disabled')
    )
    page_context = {
        **_reveal_status_context(),
        **workspace_context,
        **target_context,
        'selected_secret_name': selected_secret_name,
        'selected_key_name': request.args.get('key_name', '').strip(),
        'selected_cluster': selected_cluster,
        'selected_namespace_policy': selected_namespace_policy,
    }
    return render_template(
        'kubernetes_operations/secrets/reveal.html',
        **page_context,
    )


@any_permission_required('kubernetes_secrets.reveal', 'kubernetes_secrets.approve_reveal')
def reveal_secret_status():
    return render_template(
        'kubernetes_operations/secrets/_reveal_request_status.html',
        **_reveal_status_context(),
    )


@permission_required('kubernetes_secrets.approve_reveal')
def reveal_secret_approvals():
    return render_template(
        'kubernetes_operations/secrets/_reveal_pending_approvals.html',
        **_reveal_status_context(),
    )


@permission_required('kubernetes_secrets.reveal')
def reveal_secret_workspace():
    return render_template(
        'kubernetes_operations/secrets/_reveal_target_workspace.html',
        **get_reveal_workspace(
            request.args.get('cluster_id'),
            request.args.get('namespace'),
            request.args.get('secret_name'),
        ),
        reset_content=True,
    )


@permission_required('kubernetes_secrets.reveal')
def reveal_secret_content():
    return render_template(
        'kubernetes_operations/secrets/_reveal_request_form.html',
        step_up_active=_secret_reveal_step_up_active(),
        selected_key_name=request.args.get('key_name', '').strip(),
        **get_reveal_target_context(
            request.args.get('cluster_id'),
            request.args.get('namespace'),
            request.args.get('secret_name'),
        ),
    )


@permission_required('kubernetes_secrets.reveal')
@limiter.limit(
    lambda: current_app.config.get(
        'KUBERNETES_SECRET_REVEAL_RATE_LIMIT',
        '3 per 5 minutes',
    ),
    methods=['POST'],
    key_func=lambda: f'user:{current_user.get_id()}',
)
def request_secret_reveal():
    try:
        _validate_secret_operation_csrf()
        result = create_reveal_request(
            request.form,
            requester_user_id=current_user.id,
            requester_ip=_client_ip(),
        )
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_requested',
            status=result.status,
            title=result.title,
            message=result.message,
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Open Protected Secret Reveal',
            metadata=result.metadata,
            queue_feedback=True,
        )
        _notify_secret_reveal_approvers(result.request_record)
        return redirect(url_for('kubernetes_operations.reveal_secret'))
    except ActiveRevealRequestExists as exc:
        db.session.rollback()
        existing = exc.request_record
        action_url = url_for(
            'kubernetes_operations.reveal_secret',
            cluster_id=existing.cluster_id,
            namespace=existing.namespace,
            secret_name=existing.secret_name,
            key_name=existing.key_name,
            _anchor='my-secret-reveal-requests',
        )
        metadata = {
            **_reveal_request_metadata(existing),
            'duplicate_request_blocked': True,
            'secret_value_recorded': False,
        }
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_duplicate_request_blocked',
            status='warning',
            title='Active reveal request already exists',
            message=str(exc),
            action_url=action_url,
            action_label='Open existing request',
            metadata=metadata,
            queue_feedback=True,
        )
        return redirect(action_url)
    except ValueError as exc:
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_request_failed',
            status='error',
            title='Secret reveal request failed',
            message=str(exc),
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Review reveal request',
            metadata={
                'cluster_id': request.form.get('cluster_id'),
                'namespace': request.form.get('namespace'),
                'secret_name': request.form.get('secret_name'),
                'key_name': request.form.get('key_name'),
                'ticket_reference': request.form.get('ticket_reference'),
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
        return redirect(url_for('kubernetes_operations.reveal_secret'))
    except Exception:
        current_app.logger.exception('Unexpected protected Secret reveal request failure.')
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_request_failed',
            status='error',
            title='Secret reveal request failed',
            message='KAORI could not create the protected reveal request because of an internal error.',
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Review reveal request',
            metadata={
                'cluster_id': request.form.get('cluster_id'),
                'namespace': request.form.get('namespace'),
                'secret_name': request.form.get('secret_name'),
                'key_name': request.form.get('key_name'),
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
        return redirect(url_for('kubernetes_operations.reveal_secret'))


@permission_required('kubernetes_secrets.reveal')
@limiter.limit(
    '5 per 5 minutes',
    methods=['POST'],
    key_func=lambda: f'user:{current_user.get_id()}',
)
def reauthenticate_secret_reveal():
    try:
        _validate_secret_operation_csrf()
    except ValueError as exc:
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_reauthentication_failed',
            status='error',
            title='Reauthentication failed',
            message=str(exc),
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Retry reauthentication',
            metadata={'secret_value_recorded': False},
            queue_feedback=True,
        )
        return redirect(url_for('kubernetes_operations.reveal_secret'))

    password = request.form.get('password') or ''
    if current_user.is_external:
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_reauthentication_failed',
            status='error',
            title='Reauthentication unavailable',
            message='External authentication step-up is not available yet. Use a database-managed break-glass account.',
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Open Protected Secret Reveal',
            metadata={
                'auth_source': current_user.auth_source,
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
    elif not current_user.check_password(password):
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_reauthentication_failed',
            status='error',
            title='Reauthentication failed',
            message='The current account password is incorrect.',
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Retry reauthentication',
            metadata={
                'auth_source': current_user.auth_source,
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
    else:
        _mark_secret_reveal_step_up()
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_reauthenticated',
            status='success',
            title='Protected reveal session verified',
            message='One-time Secret reveal actions are available for the configured short session window.',
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Open Protected Secret Reveal',
            metadata={
                'auth_source': current_user.auth_source,
                'step_up_ttl_seconds': current_app.config.get('KUBERNETES_SECRET_REVEAL_STEP_UP_TTL_SECONDS', 300),
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
    return redirect(url_for('kubernetes_operations.reveal_secret'))


@permission_required('kubernetes_secrets.approve_reveal')
def decide_secret_reveal_request(request_id: str):
    decision = (request.form.get('decision') or '').strip().lower()
    try:
        _validate_secret_operation_csrf()
        if decision not in {'approve', 'deny'}:
            raise ValueError('Unsupported Secret reveal decision.')
        record = decide_reveal_request(
            request_id,
            approver_user_id=current_user.id,
            approve=decision == 'approve',
            decision_note=request.form.get('decision_note'),
        )
        approved = decision == 'approve'
        _record_secret_activity(
            event_type=('kubernetes_secret_reveal_approved' if approved else 'kubernetes_secret_reveal_denied'),
            status='success' if approved else 'warning',
            title='Secret reveal request approved' if approved else 'Secret reveal request denied',
            message=(
                'The requestor can reauthenticate and perform the one-time reveal before expiry.'
                if approved
                else 'The protected Secret reveal request was denied.'
            ),
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Review reveal requests',
            metadata=_reveal_request_metadata(record),
            queue_feedback=True,
        )
        try:
            create_notification(
                user_id=record.requester_user_id,
                event_type=('kubernetes_secret_reveal_approved' if approved else 'kubernetes_secret_reveal_denied'),
                status='success' if approved else 'warning',
                title=('Secret reveal request approved' if approved else 'Secret reveal request denied'),
                message=(
                    'Reauthenticate and use the one-time reveal action before the approved request expires.'
                    if approved
                    else 'Your protected Secret reveal request was denied.'
                ),
                action_url=url_for('kubernetes_operations.reveal_secret'),
                metadata=_reveal_request_metadata(record),
            )
        except Exception:
            # The authorization decision is already committed. Notification delivery
            # must never roll back or misreport the saved approval/denial outcome.
            current_app.logger.exception('Protected Secret reveal decision saved, but requester notification failed.')
    except ValueError as exc:
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_decision_failed',
            status='error',
            title='Secret reveal decision failed',
            message=str(exc),
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Review reveal requests',
            metadata={
                'reveal_request_id': request_id,
                'decision': decision,
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
    except Exception:
        current_app.logger.exception('Unexpected protected Secret reveal decision failure.')
        _record_secret_activity(
            event_type='kubernetes_secret_reveal_decision_failed',
            status='error',
            title='Secret reveal decision failed',
            message='KAORI could not save the reveal decision because of an internal error.',
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Review reveal requests',
            metadata={
                'reveal_request_id': request_id,
                'decision': decision,
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
    return redirect(url_for('kubernetes_operations.reveal_secret'))


@permission_required('kubernetes_secrets.reveal')
@limiter.limit(
    lambda: current_app.config.get(
        'KUBERNETES_SECRET_REVEAL_RATE_LIMIT',
        '3 per 5 minutes',
    ),
    methods=['POST'],
    key_func=lambda: f'user:{current_user.get_id()}',
)
def reveal_secret_value(request_id: str):
    feedback: dict[str, Any]
    revealed_value = None
    try:
        _validate_secret_operation_csrf()
        if not _secret_reveal_step_up_active():
            raise ValueError('Reauthenticate before performing a protected Secret reveal.')
        result = execute_secret_value_reveal(request_id, user_id=current_user.id)
        revealed_value = result
        feedback = _record_secret_activity(
            event_type='kubernetes_secret_revealed',
            status='success',
            title='Secret value revealed',
            message=(
                f'{result.key_name} was revealed once for '
                f'{result.expires_in_seconds} seconds. The value was not stored by KAORI.'
            ),
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Open Protected Secret Reveal',
            metadata=result.metadata,
        )
    except ValueError as exc:
        # A failed locking/API query can leave PostgreSQL in an aborted transaction.
        # Reset the session before reading request metadata or writing activity data.
        db.session.rollback()
        try:
            record = get_reveal_request_for_user(request_id, user_id=current_user.id)
            metadata = _reveal_request_metadata(record)
        except ValueError:
            metadata = {'reveal_request_id': request_id, 'secret_value_recorded': False}
        feedback = _record_secret_activity(
            event_type='kubernetes_secret_reveal_failed',
            status='error',
            title='Secret reveal failed',
            message=str(exc),
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Review reveal request',
            metadata=metadata,
        )
    except Exception:
        # Notification/activity persistence uses the same scoped session. Roll back
        # first so the failure record is not attempted inside an aborted transaction.
        db.session.rollback()
        current_app.logger.exception('Unexpected protected Secret reveal failure.')
        feedback = _record_secret_activity(
            event_type='kubernetes_secret_reveal_failed',
            status='error',
            title='Secret reveal failed',
            message='KAORI could not complete the protected reveal because of an internal error.',
            action_url=url_for('kubernetes_operations.reveal_secret'),
            action_label='Review reveal request',
            metadata={'reveal_request_id': request_id, 'secret_value_recorded': False},
        )

    response = make_response(
        render_template(
            'kubernetes_operations/secrets/_reveal_value.html',
            revealed_value=revealed_value,
            operation_feedback=_notification_response_context(feedback),
        )
    )
    response.headers['Cache-Control'] = 'no-store, private, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@permission_required('kubernetes_secrets.rotate_tls')
def tls_secret_rotate(certificate_id: int):
    if has_registered_clusters() is False:
        return redirect(url_for('governance.tls_certificates'))

    record = get_tls_certificate_detail(certificate_id)
    if record is None:
        _record_secret_activity(
            event_type='kubernetes_tls_secret_not_found',
            status='warning',
            title='TLS Secret Not Found',
            message='The selected TLS certificate record is no longer available.',
            action_url=url_for('governance.tls_certificates'),
            action_label='Open TLS Secrets',
            queue_feedback=True,
        )
        return redirect(url_for('governance.tls_certificates'))

    return render_template(
        'kubernetes_operations/secrets/tls_rotate.html',
        record=record,
    )


@permission_required('kubernetes_secrets.rotate_tls')
def tls_secret_rotate_preview(certificate_id: int):
    record = get_tls_certificate_detail(certificate_id)
    if record is None:
        _record_secret_activity(
            event_type='kubernetes_tls_secret_not_found',
            status='warning',
            title='TLS Secret Not Found',
            message='The selected TLS certificate record is no longer available.',
            action_url=url_for('governance.tls_certificates'),
            action_label='Open TLS Secrets',
            queue_feedback=True,
        )
        return redirect(url_for('governance.tls_certificates'))

    payload = preview_uploaded_pair(request.files, [certificate_id])
    feedback = _record_validation_activity(
        preview=payload,
        selected_ids=[certificate_id],
        record=record,
    )
    return _build_tls_rotation_preview_response(
        render_template(
            'kubernetes_operations/secrets/_update_preview.html',
            record=record,
            payload=payload,
            operation_feedback=_notification_response_context(feedback),
        ),
        payload,
    )


@permission_required('kubernetes_secrets.rotate_tls')
def tls_secret_rotate_apply(certificate_id: int):
    record = get_tls_certificate_detail(certificate_id)
    result = apply_certificate_update(certificate_id, request.files)
    is_success = result['status'] == 'success'
    cluster = getattr(record, 'cluster', None) if record is not None else None
    _record_secret_activity(
        event_type='kubernetes_tls_secret_rotation',
        status='success' if is_success else 'error',
        title='TLS Secret rotation completed' if is_success else 'TLS Secret rotation failed',
        message=(
            f'{record.secret_name} was updated successfully.'
            if is_success and record is not None
            else result['message']
        ),
        action_url=(
            url_for('governance.tls_certificates_detail', certificate_id=certificate_id)
            if record is not None
            else url_for('governance.tls_certificates')
        ),
        action_label='View certificate posture',
        metadata={
            'certificate_id': certificate_id,
            'cluster_id': getattr(record, 'cluster_id', None),
            'cluster_name': getattr(cluster, 'name', None),
            'namespace': getattr(record, 'namespace', None),
            'secret_name': getattr(record, 'secret_name', None),
            'operation': 'rotate_tls_secret',
            'updated_count': 1 if is_success else 0,
            'failed_count': 0 if is_success else 1,
        },
        queue_feedback=True,
    )
    return redirect(url_for('governance.tls_certificates_detail', certificate_id=certificate_id))


@permission_required('kubernetes_secrets.bulk_rotate_tls')
def tls_secret_bulk_rotation_page():
    if has_registered_clusters() is False:
        return redirect(url_for('governance.tls_certificates'))

    payload = get_tls_certificate_page(request.args)
    partial_mode = request.args.get('partial_mode')

    if not payload['schema_readiness']['ready'] and partial_mode:
        return render_template(
            'governance/tls_certificates/partials/_schema_blocker.html',
            payload=payload,
        ), 409

    if partial_mode == 'bulk_workspace':
        return render_template(
            'kubernetes_operations/secrets/_bulk_target_workspace.html',
            payload=payload,
            selected_ids=request.args.getlist('certificate_ids'),
        )

    if partial_mode == 'bulk_table':
        return render_template(
            'kubernetes_operations/secrets/_bulk_target_table.html',
            payload=payload,
            selected_ids=request.args.getlist('certificate_ids'),
        )

    return render_template(
        'kubernetes_operations/secrets/tls_rotation.html',
        payload=payload,
        preview=None,
        apply_result=None,
        selected_ids=[],
    )


@permission_required('kubernetes_secrets.bulk_rotate_tls')
def tls_secret_bulk_rotation_preview():
    payload = get_tls_certificate_page(request.form)
    if not payload['schema_readiness']['ready']:
        template = (
            'governance/tls_certificates/partials/_schema_blocker.html'
            if request.headers.get('HX-Request')
            else 'kubernetes_operations/secrets/tls_rotation.html'
        )
        return render_template(
            template,
            payload=payload,
            preview=None,
            apply_result=None,
            selected_ids=[],
        ), 409

    selected_ids = request.form.getlist('certificate_ids')
    parsed_ids = _parse_certificate_ids(selected_ids)
    preview = preview_uploaded_pair(request.files, parsed_ids)
    feedback = _record_validation_activity(
        preview=preview,
        selected_ids=parsed_ids,
    )
    operation_feedback = _notification_response_context(feedback)

    if request.headers.get('HX-Request'):
        return render_template(
            'kubernetes_operations/secrets/_bulk_feedback.html',
            payload=payload,
            preview=preview,
            apply_result=None,
            selected_ids=selected_ids,
            operation_feedback=operation_feedback,
        )

    return render_template(
        'kubernetes_operations/secrets/tls_rotation.html',
        payload=payload,
        preview=preview,
        apply_result=None,
        selected_ids=selected_ids,
        operation_feedback=operation_feedback,
    )


@permission_required('kubernetes_secrets.bulk_rotate_tls')
def tls_secret_bulk_rotation_apply():
    payload = get_tls_certificate_page(request.form)
    if not payload['schema_readiness']['ready']:
        template = (
            'governance/tls_certificates/partials/_schema_blocker.html'
            if request.headers.get('HX-Request')
            else 'kubernetes_operations/secrets/tls_rotation.html'
        )
        return render_template(
            template,
            payload=payload,
            preview=None,
            apply_result=None,
            selected_ids=[],
        ), 409

    selected_ids = request.form.getlist('certificate_ids')
    parsed_ids = _parse_certificate_ids(selected_ids)
    apply_result = apply_bulk_update(request.files, parsed_ids)
    results = apply_result.get('results') or []
    success_count = sum(1 for item in results if item.get('status') == 'success')
    failed_count = len(results) - success_count
    is_success = failed_count == 0 and success_count > 0
    is_warning = success_count > 0 and failed_count > 0
    status = 'success' if is_success else 'warning' if is_warning else 'error'
    title = (
        'Bulk TLS Secret rotation completed'
        if is_success
        else 'Bulk TLS Secret rotation completed with warnings'
        if is_warning
        else 'Bulk TLS Secret rotation failed'
    )
    feedback = _record_secret_activity(
        event_type='kubernetes_tls_secret_bulk_rotation',
        status=status,
        title=title,
        message=apply_result['message'],
        action_url=url_for('kubernetes_operations.tls_secret_bulk_rotation'),
        action_label='Review TLS rotation workspace',
        metadata={
            'bulk_job_id': apply_result.get('bulk_job_id'),
            'operation': 'bulk_rotate_tls_secret',
            'target_count': len(parsed_ids),
            'updated_count': success_count,
            'failed_count': failed_count,
            'failed_targets': [
                item['target'].secret_name
                for item in results
                if item.get('status') != 'success' and item.get('target') is not None
            ],
        },
    )
    operation_feedback = _notification_response_context(feedback)

    if request.headers.get('HX-Request'):
        return render_template(
            'kubernetes_operations/secrets/_bulk_feedback.html',
            payload=payload,
            preview=None,
            apply_result=apply_result,
            selected_ids=selected_ids,
            operation_feedback=operation_feedback,
        )

    return render_template(
        'kubernetes_operations/secrets/tls_rotation.html',
        payload=payload,
        preview=None,
        apply_result=apply_result,
        selected_ids=selected_ids,
        operation_feedback=operation_feedback,
    )
