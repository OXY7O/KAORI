from __future__ import annotations

from typing import Any

from flask import make_response, redirect, render_template, request, url_for

from app.cluster.onboarding import has_registered_clusters
from app.kubernetes_operations.secrets.route_support import (
    notification_response_context as _notification_response_context,
    record_secret_activity as _record_secret_activity,
    validate_secret_operation_csrf as _validate_secret_operation_csrf,
)
from app.kubernetes_operations.secrets.tls_validation import validation_trigger
from app.governance.tls_certificates.service import (
    get_tls_certificate_detail,
    get_tls_certificate_page,
)
from app.governance.tls_certificates.updates import (
    apply_bulk_update,
    apply_certificate_update,
    preview_uploaded_pair,
)
from app.rbac.decorators import permission_required
def _parse_certificate_ids(values: list[str]) -> list[int]:
    normalized_values = (value.strip() for value in values)
    return [int(value) for value in normalized_values if value.isdigit()]



def _tls_workspace_redirect(location: str):
    """Return a full-page redirect so TLS workflows restart from clean state."""
    if request.headers.get('HX-Request') == 'true':
        response = make_response('', 204)
        response.headers['HX-Redirect'] = location
        return response
    return redirect(location)


def _tls_csrf_guard(location: str):
    try:
        _validate_secret_operation_csrf()
    except ValueError as exc:
        _record_secret_activity(
            event_type='kubernetes_tls_secret_csrf_failed',
            status='error',
            title='TLS Secret operation expired',
            message=str(exc),
            action_url=location,
            action_label='Reload TLS rotation',
            metadata={
                'operation': 'csrf_validation',
                'secret_value_recorded': False,
            },
            queue_feedback=True,
        )
        return _tls_workspace_redirect(location)
    return None


def _build_tls_rotation_preview_response(rendered_html: str, payload: dict[str, Any]):
    response = make_response(rendered_html)
    trigger = validation_trigger(payload, form_id='tls-secret-rotate-form')
    if trigger is not None:
        response.headers['HX-Trigger'] = trigger
    return response


def _build_bulk_tls_rotation_preview_response(
    rendered_html: str,
    preview: dict[str, Any],
):
    response = make_response(rendered_html)
    trigger = validation_trigger(
        preview,
        form_id='tls-secret-update-form',
        require_targets=True,
    )
    if trigger is not None:
        response.headers['HX-Trigger'] = trigger
    return response



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
    csrf_failure = _tls_csrf_guard(
        url_for('kubernetes_operations.tls_secret_rotate', certificate_id=certificate_id)
    )
    if csrf_failure is not None:
        return csrf_failure
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
    csrf_failure = _tls_csrf_guard(
        url_for('kubernetes_operations.tls_secret_rotate', certificate_id=certificate_id)
    )
    if csrf_failure is not None:
        return csrf_failure
    record = get_tls_certificate_detail(certificate_id)
    cluster = getattr(record, 'cluster', None) if record is not None else None
    target_metadata = {
        'certificate_id': certificate_id,
        'cluster_id': getattr(record, 'cluster_id', None),
        'cluster_name': getattr(cluster, 'name', None),
        'namespace': getattr(record, 'namespace', None),
        'secret_name': getattr(record, 'secret_name', None),
    }
    result = apply_certificate_update(certificate_id, request.files)
    result_status = result['status']
    is_success = result_status == 'success'
    is_warning = result_status == 'warning'
    provider_updated = result.get('provider_updated') is True
    title = (
        'TLS Secret rotation completed'
        if is_success
        else 'TLS Secret rotation requires synchronization'
        if is_warning
        else 'TLS Secret rotation failed'
    )
    _record_secret_activity(
        event_type='kubernetes_tls_secret_rotation',
        status='success' if is_success else 'warning' if is_warning else 'error',
        title=title,
        message=(
            f"{target_metadata['secret_name']} was updated successfully."
            if is_success and target_metadata['secret_name']
            else result['message']
        ),
        action_url=(
            url_for('governance.tls_certificates_detail', certificate_id=certificate_id)
            if record is not None
            else url_for('governance.tls_certificates')
        ),
        action_label='View certificate posture',
        metadata={
            **target_metadata,
            'operation': 'rotate_tls_secret',
            'updated_count': 1 if provider_updated else 0,
            'failed_count': 0 if provider_updated else 1,
            'persistence_gap_count': 1 if provider_updated and not result.get('persistence_confirmed') else 0,
            'provider_updated': provider_updated,
            'persistence_confirmed': result.get('persistence_confirmed'),
        },
        queue_feedback=True,
    )
    if is_success:
        return _tls_workspace_redirect(
            url_for('kubernetes_operations.tls_secret_rotate', certificate_id=certificate_id)
        )
    return redirect(url_for('governance.tls_certificates_detail', certificate_id=certificate_id))


@permission_required('kubernetes_secrets.bulk_rotate_tls')
def tls_secret_bulk_rotation_page():
    if has_registered_clusters() is False:
        return redirect(url_for('governance.tls_certificates'))

    payload = get_tls_certificate_page(request.args)
    partial_mode = request.args.get('partial_mode')

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
    csrf_failure = _tls_csrf_guard(
        url_for('kubernetes_operations.tls_secret_bulk_rotation')
    )
    if csrf_failure is not None:
        return csrf_failure
    payload = get_tls_certificate_page(request.form)
    selected_ids = request.form.getlist('certificate_ids')
    parsed_ids = _parse_certificate_ids(selected_ids)
    preview = preview_uploaded_pair(request.files, parsed_ids)
    feedback = _record_validation_activity(
        preview=preview,
        selected_ids=parsed_ids,
    )
    operation_feedback = _notification_response_context(feedback)

    if request.headers.get('HX-Request'):
        rendered_html = render_template(
            'kubernetes_operations/secrets/_bulk_feedback.html',
            payload=payload,
            preview=preview,
            apply_result=None,
            selected_ids=selected_ids,
            operation_feedback=operation_feedback,
        )
        return _build_bulk_tls_rotation_preview_response(rendered_html, preview)

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
    csrf_failure = _tls_csrf_guard(
        url_for('kubernetes_operations.tls_secret_bulk_rotation')
    )
    if csrf_failure is not None:
        return csrf_failure
    payload = get_tls_certificate_page(request.form)
    selected_ids = request.form.getlist('certificate_ids')
    parsed_ids = _parse_certificate_ids(selected_ids)
    apply_result = apply_bulk_update(request.files, parsed_ids)
    results = apply_result.get('results') or []
    success_count = sum(1 for item in results if item.get('status') == 'success')
    warning_count = sum(1 for item in results if item.get('status') == 'warning')
    failed_count = sum(1 for item in results if item.get('status') == 'failed')
    provider_updated_count = success_count + warning_count
    is_success = apply_result.get('status') == 'success'
    is_warning = apply_result.get('status') == 'warning'
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
            'updated_count': provider_updated_count,
            'failed_count': failed_count,
            'persistence_gap_count': warning_count,
            'failed_targets': [
                item['target'].secret_name
                for item in results
                if item.get('status') == 'failed' and item.get('target') is not None
            ],
        },
        queue_feedback=is_success,
    )

    if is_success:
        return _tls_workspace_redirect(
            url_for('kubernetes_operations.tls_secret_bulk_rotation')
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
