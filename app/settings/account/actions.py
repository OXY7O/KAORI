from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flask import current_app, session, url_for
from sqlalchemy import select

from app.access.authentication.admission import session_admission_reason
from app.access.authentication.forms import ChangePasswordForm
from app.access.authentication.session import (
    AuthSessionError,
    parse_authenticated_user_identifier,
    preserve_current_session_after_password_change,
)
from app.access.authentication.session_lifecycle import SessionDeadlines, read_session_policy, session_deadlines
from app.extensions.db import db
from app.models import User
from app.platform_operations.notifications.feedback import (
    OperationalActionPresentation,
    OperationalDeliveryPolicy,
    queue_operational_feedback,
)
from app.platform_operations.notifications.service import (
    create_transient_feedback,
    record_operational_activity,
    stage_operational_activity,
)


@dataclass(slots=True)
class PasswordActionResult:
    form: ChangePasswordForm
    inline_feedback: dict[str, str] | None = None
    toast: dict[str, Any] | None = None
    notification_changed: bool = False
    saved: bool = False


def _record_password_change_rejection(
    *,
    user: User,
    auth_source: str,
    reason_code: str,
    is_htmx: bool,
    title: str = 'Account password change rejected',
    message: str = 'KAORI rejected a Local Database password change attempt for this account.',
    status: str = 'error',
) -> dict[str, Any]:
    return record_operational_activity(
        user_id=user.id,
        event_type='account_security',
        status=status,
        title=title,
        message=message,
        detail='No credential or session state was changed.',
        action_url=url_for('settings.account', tab='credentials'),
        action_label='Open Credential Management',
        action_icon='key-round',
        metadata={
            'security_action': 'password_change',
            'credential_owner': 'KAORI Local Database' if auth_source == 'database' else 'External Identity Provider',
            'auth_source': auth_source,
            'result': 'failed',
            'reason_code': reason_code,
        },
        queue_feedback=not is_htmx,
        delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
    )


def _commit_local_password_change(user: User, new_password: str) -> tuple[int, int, dict[str, Any]]:
    """Commit the replacement credential, exact generation and audit together."""
    user_id = user.id
    verified_hash = user.password_hash
    try:
        session_user_id, generation = parse_authenticated_user_identifier(session.get('_user_id'))
    except ValueError as exc:
        raise AuthSessionError('Current session is not admitted.') from exc
    if session_user_id != user_id or generation is None:
        raise AuthSessionError('Current session is not admitted.')

    # Lock the authoritative row; a concurrent login, credential replacement
    # or lifecycle change must not let an old proof replace a newer credential.
    locked = db.session.execute(
        select(User)
        .where(
            User.id == user_id,
            User.auth_session_version == generation,
            User.password_hash == verified_hash,
            User.auth_source == 'database',
            User.account_is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .with_for_update(of=User)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if locked is None or session_admission_reason(locked, source='database') is not None:
        raise AuthSessionError('Current session is no longer admitted.')
    policy = read_session_policy()
    if not isinstance(session_deadlines(locked, policy, datetime.now(UTC)), SessionDeadlines):
        raise AuthSessionError('Current session is no longer admitted.')

    locked.set_password(new_password)
    issued_generation = locked.auth_session_version
    if issued_generation != generation + 1:
        raise AuthSessionError('Credential generation could not be advanced.')
    # Password rotation must not reset the absolute age or revive idle expiry.
    if not isinstance(session_deadlines(locked, policy, datetime.now(UTC)), SessionDeadlines):
        raise AuthSessionError('Current session is no longer admitted.')
    feedback = stage_operational_activity(
        user_id=user_id,
        event_type='account_security',
        status='success',
        title='Account password updated',
        message='Your KAORI Local Database password was changed successfully.',
        action_url=url_for('settings.account', tab='credentials'),
        action=OperationalActionPresentation(label='Open Credential Management', icon='key-round'),
        metadata={
            'security_action': 'password_change',
            'credential_owner': 'KAORI Local Database',
            'auth_source': 'database',
            'result': 'success',
            'session_effect': 'other_sessions_revoked',
            'current_session': 'preserved',
            'remembered_sign_ins': 'revoked',
            'auth_session_version': issued_generation,
        },
    )
    db.session.commit()
    return user_id, issued_generation, feedback


def process_password_change(
    *,
    user: User,
    form: ChangePasswordForm,
    auth_source: str,
    is_htmx: bool,
) -> PasswordActionResult:
    if auth_source != 'database':
        feedback = _record_password_change_rejection(
            user=user,
            auth_source=auth_source,
            reason_code='external_credential_owner',
            title='Password is managed externally',
            message='Use the connected identity provider to change or recover this account credential.',
            status='warning',
            is_htmx=is_htmx,
        )
        return PasswordActionResult(
            form=form,
            inline_feedback={
                'status': 'warning',
                'title': 'Password is managed externally',
                'message': (
                    'This account uses an external authentication source. Password updates must be completed '
                    'in the connected identity provider.'
                ),
            },
            toast=feedback if is_htmx else None,
        )

    if not form.validate():
        feedback = create_transient_feedback(
            status='error',
            title='Password update failed',
            message='Review the password requirements and highlighted fields before trying again.',
            action_url=url_for('settings.account', tab='credentials'),
            action_label='Review Credential Management',
            action_icon='key-round',
            queue_feedback=not is_htmx,
        )
        return PasswordActionResult(
            form=form,
            inline_feedback={
                'status': 'danger',
                'title': 'Password update failed',
                'message': 'Review the password requirements and highlighted fields before trying again.',
            },
            toast=feedback if is_htmx else None,
        )

    current_password = form.current_password.data or ''
    new_password = form.new_password.data or ''
    if not user.check_password(current_password):
        form.current_password.errors = [*form.current_password.errors, 'Current password is incorrect.']
        feedback = _record_password_change_rejection(
            user=user,
            auth_source=auth_source,
            reason_code='current_password_mismatch',
            is_htmx=is_htmx,
        )
        return PasswordActionResult(
            form=form,
            inline_feedback={
                'status': 'danger',
                'title': 'Password update failed',
                'message': 'The current password does not match the active local account password.',
            },
            toast=feedback if is_htmx else None,
        )

    if user.check_password(new_password):
        form.new_password.errors = [
            *form.new_password.errors,
            'New password must be different from the current password.',
        ]
        feedback = _record_password_change_rejection(
            user=user,
            auth_source=auth_source,
            reason_code='current_password_reuse',
            is_htmx=is_htmx,
        )
        return PasswordActionResult(
            form=form,
            inline_feedback={
                'status': 'danger',
                'title': 'Password update failed',
                'message': 'Choose a new Local Database password instead of reusing the active credential.',
            },
            toast=feedback if is_htmx else None,
        )

    try:
        user_id, issued_generation, feedback = _commit_local_password_change(user, new_password)
    except Exception:
        # The success audit is part of the credential transaction. Do not log
        # exception payloads that could include sensitive SQL bind parameters.
        db.session.rollback()
        current_app.logger.warning('Account credential transaction could not be completed.')
        message = 'Password update could not be committed. Sign in again and retry.'
        failed_feedback = create_transient_feedback(
            status='error',
            title='Password update failed',
            message=message,
            queue_feedback=not is_htmx,
        )
        return PasswordActionResult(
            form=form,
            inline_feedback={'status': 'danger', 'title': 'Password update failed', 'message': message},
            toast=failed_feedback if is_htmx else None,
        )

    # Pin this browser to the generation minted by this transaction, never
    # the ORM's possibly newer generation after commit.
    preserve_current_session_after_password_change(user_id=user_id, issued_session_version=issued_generation)
    feedback['detail'] = (
        'This browser remains bound to the committed generation. Other authenticated sessions and '
        'remembered sign-ins were revoked. Password values are excluded from audit metadata.'
    )
    if not is_htmx:
        queue_operational_feedback(feedback)
    return PasswordActionResult(
        form=ChangePasswordForm() if is_htmx else form,
        toast=feedback if is_htmx else None,
        notification_changed=bool(feedback.get('notification_deck_visible')),
        saved=True,
    )
