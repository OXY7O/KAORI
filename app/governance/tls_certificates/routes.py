from __future__ import annotations

from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.cluster.onboarding import has_registered_clusters
from app.governance.tls_certificates.service import (
    apply_bulk_update,
    apply_certificate_update,
    get_tls_certificate_detail,
    get_tls_certificate_page,
    preview_uploaded_pair,
    sync_tls_certificates,
)
from app.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.rbac.decorators import permission_required


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


def _record_tls_activity(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    action_label: str = 'Open TLS inventory',
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
        action_url=action_url or url_for('governance.tls_certificates'),
        action_label=action_label,
        action_icon='shield-check',
        metadata=metadata,
        queue_feedback=queue_feedback,
    )


def _record_validation_activity(
    *,
    preview: dict[str, Any],
    selected_ids: list[int],
    record: Any | None = None,
) -> dict[str, Any]:
    validation = preview['validation']
    target_previews = preview.get('targets') or []
    uncovered_hosts = sorted(
        {
            host
            for target_preview in target_previews
            for host in (target_preview.get('uncovered_hosts') or [])
        }
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
    return _record_tls_activity(
        event_type='governance_tls_secret_validation',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=(
            url_for('governance.tls_certificates_detail', certificate_id=record.id)
            if record is not None
            else url_for('governance.tls_certificates_bulk_update')
        ),
        action_label='Review TLS validation',
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
                parsed.not_after.isoformat()
                if parsed is not None and parsed.not_after is not None
                else None
            ),
        },
    )


@permission_required('tls_certificates.view')
def tls_certificates_index():
    payload = get_tls_certificate_page(request.args)
    partial_mode = request.args.get('partial_mode')

    if partial_mode == 'content':
        return render_template(
            'governance/tls_certificates/partials/_content.html',
            payload=payload,
        )

    if partial_mode == 'table':
        return render_template(
            'governance/tls_certificates/partials/_table.html',
            payload=payload,
        )

    return render_template(
        'governance/tls_certificates/index.html',
        payload=payload,
    )


@permission_required('tls_certificates.view')
def tls_certificates_detail(certificate_id: int):
    if has_registered_clusters() is False:
        return redirect(url_for('governance.tls_certificates'))

    record = get_tls_certificate_detail(certificate_id)
    if record is None:
        flash('TLS certificate record was not found.', 'warning')
        return redirect(url_for('governance.tls_certificates'))

    return render_template(
        'governance/tls_certificates/detail.html',
        record=record,
    )


@permission_required('tls_certificates.sync')
def tls_certificates_sync():
    cluster_id = request.form.get('cluster_id') or None
    result = sync_tls_certificates(cluster_id)
    has_errors = bool(result['errors'])
    status = 'warning' if has_errors else 'success'
    title = 'TLS Secret sync completed with warnings' if has_errors else 'TLS Secret sync completed'
    message = (
        f'{result["total"]} Kubernetes TLS Secrets were collected. '
        f'{len(result["errors"])} cluster syncs require review.'
        if has_errors
        else f'{result["total"]} Kubernetes TLS Secrets were collected successfully.'
    )
    detail = '; '.join(result['errors']) if has_errors else None

    selected_cluster_name = result['results'][0]['cluster'] if cluster_id and result['results'] else None

    feedback = _record_tls_activity(
        event_type='governance_tls_secret_sync',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('governance.tls_certificates', cluster_id=cluster_id or ''),
        metadata={
            'cluster_id': cluster_id,
            'cluster_name': selected_cluster_name,
            'cluster_scope': 'selected_cluster' if cluster_id else 'all_clusters',
            'collected_count': result['total'],
            'failed_cluster_count': len(result['errors']),
        },
    )

    if request.headers.get('HX-Request'):
        payload = get_tls_certificate_page({'cluster_id': cluster_id or ''})
        return render_template(
            'governance/tls_certificates/partials/_page_content.html',
            payload=payload,
            sync_feedback={
                **feedback,
                'status': status,
                'title': title,
                'message': message,
                'detail': detail,
                'notification_context': get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            },
        )

    flash(f'{title}. {message}', status)
    return redirect(url_for('governance.tls_certificates', cluster_id=cluster_id or ''))


@permission_required('tls_certificates.update')
def tls_certificates_update_preview(certificate_id: int):
    record = get_tls_certificate_detail(certificate_id)
    if record is None:
        flash('TLS certificate record was not found.', 'warning')
        return redirect(url_for('governance.tls_certificates'))

    payload = preview_uploaded_pair(request.files, [certificate_id])
    feedback = _record_validation_activity(
        preview=payload,
        selected_ids=[certificate_id],
        record=record,
    )
    return render_template(
        'governance/tls_certificates/partials/_update_preview.html',
        record=record,
        payload=payload,
        operation_feedback=_notification_response_context(feedback),
    )


@permission_required('tls_certificates.update')
def tls_certificates_update_apply(certificate_id: int):
    record = get_tls_certificate_detail(certificate_id)
    result = apply_certificate_update(certificate_id, request.files)
    is_success = result['status'] == 'success'
    cluster = getattr(record, 'cluster', None) if record is not None else None
    feedback = _record_tls_activity(
        event_type='governance_tls_secret_update',
        status='success' if is_success else 'error',
        title='TLS Secret update completed' if is_success else 'TLS Secret update failed',
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
        action_label='Open TLS Secret record',
        metadata={
            'certificate_id': certificate_id,
            'cluster_id': getattr(record, 'cluster_id', None),
            'cluster_name': getattr(cluster, 'name', None),
            'namespace': getattr(record, 'namespace', None),
            'secret_name': getattr(record, 'secret_name', None),
            'updated_count': 1 if is_success else 0,
            'failed_count': 0 if is_success else 1,
        },
        queue_feedback=True,
    )
    flash(feedback['message'], 'success' if is_success else 'danger')
    return redirect(url_for('governance.tls_certificates_detail', certificate_id=certificate_id))


@permission_required('tls_certificates.bulk_update')
def tls_certificates_bulk_page():
    if has_registered_clusters() is False:
        return redirect(url_for('governance.tls_certificates'))

    payload = get_tls_certificate_page(request.args)
    partial_mode = request.args.get('partial_mode')

    if partial_mode == 'bulk_workspace':
        return render_template(
            'governance/tls_certificates/partials/_bulk_target_workspace.html',
            payload=payload,
            selected_ids=request.args.getlist('certificate_ids'),
        )

    if partial_mode == 'bulk_table':
        return render_template(
            'governance/tls_certificates/partials/_bulk_target_table.html',
            payload=payload,
            selected_ids=request.args.getlist('certificate_ids'),
        )

    return render_template(
        'governance/tls_certificates/bulk_update.html',
        payload=payload,
        preview=None,
        apply_result=None,
        selected_ids=[],
    )


@permission_required('tls_certificates.bulk_update')
def tls_certificates_bulk_preview():
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
        return render_template(
            'governance/tls_certificates/partials/_bulk_feedback.html',
            payload=payload,
            preview=preview,
            apply_result=None,
            selected_ids=selected_ids,
            operation_feedback=operation_feedback,
        )

    return render_template(
        'governance/tls_certificates/bulk_update.html',
        payload=payload,
        preview=preview,
        apply_result=None,
        selected_ids=selected_ids,
        operation_feedback=operation_feedback,
    )


@permission_required('tls_certificates.bulk_update')
def tls_certificates_bulk_apply():
    payload = get_tls_certificate_page(request.form)
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
        'Bulk TLS Secret update completed'
        if is_success
        else 'Bulk TLS Secret update completed with warnings'
        if is_warning
        else 'Bulk TLS Secret update failed'
    )
    feedback = _record_tls_activity(
        event_type='governance_tls_secret_bulk_update',
        status=status,
        title=title,
        message=apply_result['message'],
        action_url=url_for('governance.tls_certificates_bulk_update'),
        action_label='Review TLS update workspace',
        metadata={
            'bulk_job_id': apply_result.get('bulk_job_id'),
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
            'governance/tls_certificates/partials/_bulk_feedback.html',
            payload=payload,
            preview=None,
            apply_result=apply_result,
            selected_ids=selected_ids,
            operation_feedback=operation_feedback,
        )

    return render_template(
        'governance/tls_certificates/bulk_update.html',
        payload=payload,
        preview=None,
        apply_result=apply_result,
        selected_ids=selected_ids,
        operation_feedback=operation_feedback,
    )
