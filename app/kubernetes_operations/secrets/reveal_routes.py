from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import (
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user

from app.extensions.db import db
from app.extensions.limiter import limiter
from app.kubernetes_operations.operation_flow import cluster_required
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
from app.kubernetes_operations.secrets.route_support import (
    notification_response_context as _notification_response_context,
)
from app.kubernetes_operations.secrets.route_support import (
    record_secret_activity as _record_secret_activity,
)
from app.kubernetes_operations.secrets.route_support import (
    validate_secret_operation_csrf as _validate_secret_operation_csrf,
)
from app.models.user import User
from app.notifications.service import create_notification, get_navigation_notification_context
from app.rbac.decorators import any_permission_required, permission_required

_SECRET_REVEAL_STEP_UP_SESSION_KEY = 'kubernetes_secret_reveal_step_up'


def _client_ip() -> str | None:
    """Return the proxy-normalized client address owned by Flask/Werkzeug.

    Forwarded client headers are normalized only by trusted ProxyFix middleware
    at the application boundary, never parsed inside this route.
    """
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
            pending_per_page=request.args.get('pending_per_page', 3, type=int) or 3,
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
@cluster_required('Protected Secret Reveal')
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
@cluster_required('Protected Secret Reveal')
def reveal_secret_status():
    return render_template(
        'kubernetes_operations/secrets/_reveal_request_status.html',
        **_reveal_status_context(),
    )


@permission_required('kubernetes_secrets.approve_reveal')
@cluster_required('Protected Secret Reveal')
def reveal_secret_approvals():
    return render_template(
        'kubernetes_operations/secrets/_reveal_pending_approvals.html',
        **_reveal_status_context(),
    )


@permission_required('kubernetes_secrets.reveal')
@cluster_required('Protected Secret Reveal')
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
@cluster_required('Protected Secret Reveal')
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
@cluster_required('Protected Secret Reveal')
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
@cluster_required('Protected Secret Reveal')
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
@cluster_required('Protected Secret Reveal')
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
@cluster_required('Protected Secret Reveal')
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
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    return response
