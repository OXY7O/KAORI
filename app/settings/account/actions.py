from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import url_for

from app.access.authentication.forms import ChangePasswordForm
from app.access.authentication.session import preserve_current_session_after_password_change
from app.extensions.db import db
from app.models import User
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import create_transient_feedback, record_operational_activity


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

    user.set_password(new_password)
    db.session.commit()
    preserve_current_session_after_password_change(user)
    feedback = record_operational_activity(
        user_id=user.id,
        event_type='account_security',
        status='success',
        title='Account password updated',
        message='Your KAORI Local Database password was changed successfully.',
        detail=(
            'This browser session remains active. Other authenticated sessions and remembered sign-ins '
            'were revoked. The password value was not stored in notification or audit metadata.'
        ),
        action_url=url_for('settings.account', tab='credentials'),
        action_label='Open Credential Management',
        action_icon='key-round',
        metadata={
            'security_action': 'password_change',
            'credential_owner': 'KAORI Local Database',
            'auth_source': auth_source,
            'result': 'success',
            'session_effect': 'other_sessions_revoked',
            'current_session': 'preserved',
            'remembered_sign_ins': 'revoked',
            'auth_session_version': user.auth_session_version,
        },
        queue_feedback=not is_htmx,
    )
    return PasswordActionResult(
        form=ChangePasswordForm() if is_htmx else form,
        toast=feedback if is_htmx else None,
        notification_changed=bool(feedback.get('notification_deck_visible')),
        saved=True,
    )
