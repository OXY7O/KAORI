from __future__ import annotations

from typing import Any

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

    is_htmx = bool(request.headers.get('HX-Request'))
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




# Compatibility delegates. New navigation and templates use Kubernetes Operations.
def tls_certificates_update_preview(certificate_id: int):
    from app.kubernetes_operations.secrets.routes import tls_secret_rotate_preview

    return tls_secret_rotate_preview(certificate_id)


def tls_certificates_update_apply(certificate_id: int):
    from app.kubernetes_operations.secrets.routes import tls_secret_rotate_apply

    return tls_secret_rotate_apply(certificate_id)


def tls_certificates_bulk_page():
    return redirect(url_for('kubernetes_operations.tls_secret_bulk_rotation'), code=302)


def tls_certificates_bulk_preview():
    from app.kubernetes_operations.secrets.routes import tls_secret_bulk_rotation_preview

    return tls_secret_bulk_rotation_preview()


def tls_certificates_bulk_apply():
    from app.kubernetes_operations.secrets.routes import tls_secret_bulk_rotation_apply

    return tls_secret_bulk_rotation_apply()
