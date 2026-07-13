from __future__ import annotations

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

    feedback = record_operational_activity(
        user_id=current_user.id,
        event_type='governance_tls_secret_sync',
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('governance.tls_certificates', cluster_id=cluster_id or ''),
        action_label='Open TLS inventory',
        action_icon='shield-check',
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
        notification_context = get_navigation_notification_context(
            user_id=current_user.id,
        )
        return render_template(
            'governance/tls_certificates/partials/_page_content.html',
            payload=payload,
            sync_feedback={
                **feedback,
                'status': status,
                'title': title,
                'message': message,
                'detail': detail,
                'notification_context': notification_context,
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
    return render_template(
        'governance/tls_certificates/partials/_update_preview.html',
        record=record,
        payload=payload,
    )


@permission_required('tls_certificates.update')
def tls_certificates_update_apply(certificate_id: int):
    result = apply_certificate_update(certificate_id, request.files)
    flash(result['message'], 'success' if result['status'] == 'success' else 'danger')
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
    preview = preview_uploaded_pair(request.files, _parse_certificate_ids(selected_ids))

    if request.headers.get('HX-Request'):
        return render_template(
            'governance/tls_certificates/partials/_bulk_feedback.html',
            payload=payload,
            preview=preview,
            apply_result=None,
            selected_ids=selected_ids,
        )

    return render_template(
        'governance/tls_certificates/bulk_update.html',
        payload=payload,
        preview=preview,
        apply_result=None,
        selected_ids=selected_ids,
    )


@permission_required('tls_certificates.bulk_update')
def tls_certificates_bulk_apply():
    payload = get_tls_certificate_page(request.form)
    selected_ids = request.form.getlist('certificate_ids')
    apply_result = apply_bulk_update(request.files, _parse_certificate_ids(selected_ids))

    if request.headers.get('HX-Request'):
        return render_template(
            'governance/tls_certificates/partials/_bulk_feedback.html',
            payload=payload,
            preview=None,
            apply_result=apply_result,
            selected_ids=selected_ids,
        )

    return render_template(
        'governance/tls_certificates/bulk_update.html',
        payload=payload,
        preview=None,
        apply_result=apply_result,
        selected_ids=selected_ids,
    )
