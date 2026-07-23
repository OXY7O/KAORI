from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.cluster.onboarding import has_registered_clusters
from app.governance.tls_certificates.service import (
    get_tls_certificate_detail,
    get_tls_certificate_page,
    sync_tls_certificates,
)
from app.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.rbac.decorators import permission_required


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

    is_htmx = bool(request.headers.get('HX-Request'))
    feedback = record_operational_activity(
        user_id=current_user.id,
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
        queue_feedback=not is_htmx,
    )

    if is_htmx:
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

    return redirect(url_for('governance.tls_certificates', cluster_id=cluster_id or ''))
