from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.auth.forms import ChangePasswordForm
from app.auth.session import preserve_current_session_after_password_change
from app.common.timezone import (
    format_user_datetime,
    is_valid_timezone_name,
    normalize_date_format,
    normalize_locale,
    normalize_time_format,
    normalize_timezone_mode,
    normalize_timezone_name,
    timezone_choice_groups,
)
from app.extensions.db import db
from app.models import Notification, User
from app.notifications.feedback import OperationalDeliveryPolicy
from app.notifications.service import record_operational_activity
from app.settings.general.forms import RegionalFormatForm, TimezonePreferenceForm
from app.settings.system_information import build_system_information
from app.users.service import build_user_identity_context

bp = Blueprint(
    'settings',
    __name__,
    url_prefix='/settings',
)


def _record_password_change_rejection(*, user: User, auth_source: str, reason_code: str) -> None:
    """Persist a security-relevant self-service rejection without creating inbox noise."""

    record_operational_activity(
        user_id=user.id,
        event_type='account_security',
        status='error',
        title='Account password change rejected',
        message='KAORI rejected a Local Database password change attempt for this account.',
        detail='No credential or session state was changed.',
        action_url=url_for('settings.account', tab='credentials'),
        action_label='Open Credential Management',
        action_icon='key-round',
        metadata={
            'security_action': 'password_change',
            'credential_owner': 'KAORI Local Database',
            'auth_source': auth_source,
            'result': 'failed',
            'reason_code': reason_code,
        },
        delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
    )


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/general', methods=['GET', 'POST'])
@login_required
def general():
    user = cast(User, current_user._get_current_object())
    active_tab = (request.args.get('tab') or 'time-locale').strip().lower()
    can_view_system_information = user.has_permission('system.view')
    allowed_tabs = {'time-locale', 'regional-format'}
    if can_view_system_information:
        allowed_tabs.update({'system-information', 'compatibility-versions'})
    if active_tab not in allowed_tabs:
        active_tab = 'time-locale'

    timezone_form = TimezonePreferenceForm()
    regional_form = RegionalFormatForm()
    notification_changed = False
    general_settings_saved = False
    operation_feedback: dict[str, Any] | None = None

    timezone_submission = (
        request.method == 'POST' and active_tab == 'time-locale' and bool(timezone_form.submit_timezone.data)
    )
    regional_submission = (
        request.method == 'POST' and active_tab == 'regional-format' and bool(regional_form.submit_regional.data)
    )

    if not timezone_submission:
        timezone_form.timezone_mode.data = normalize_timezone_mode(user.timezone_mode)
        timezone_form.timezone.data = normalize_timezone_name(user.timezone)
    if not regional_submission:
        regional_form.locale.data = normalize_locale(user.locale)
        regional_form.date_format.data = normalize_date_format(user.date_format)
        regional_form.time_format.data = normalize_time_format(user.time_format)

    if timezone_submission and timezone_form.validate_on_submit():
        timezone_mode = normalize_timezone_mode(timezone_form.timezone_mode.data)
        requested_timezone = (
            timezone_form.browser_timezone.data if timezone_mode == 'automatic' else timezone_form.timezone.data
        )

        if not is_valid_timezone_name(requested_timezone):
            timezone_form.timezone.errors = ['The selected or detected browser timezone is not a valid IANA timezone.']
        else:
            user.timezone_mode = timezone_mode
            user.timezone = normalize_timezone_name(requested_timezone)
            db.session.commit()
            operation_feedback = record_operational_activity(
                user_id=user.id,
                event_type='user_preference',
                status='success',
                title='Time Zone Preference Saved',
                message=(f'KAORI now renders time-related information for this account using {user.timezone}.'),
                action_url=url_for('settings.general', tab='time-locale'),
                action_label='Open General Settings',
                action_icon='settings-2',
                metadata={
                    'preference': 'timezone',
                    'timezone_mode': user.timezone_mode,
                    'timezone': user.timezone,
                },
                queue_feedback=not bool(request.headers.get('HX-Request')),
                delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
            )
            notification_changed = bool(operation_feedback.get('notification_deck_visible'))
            general_settings_saved = True
            if not request.headers.get('HX-Request'):
                return redirect(url_for('settings.general', tab='time-locale'))

            timezone_form = TimezonePreferenceForm()
            timezone_form.timezone_mode.data = normalize_timezone_mode(user.timezone_mode)
            timezone_form.timezone.data = normalize_timezone_name(user.timezone)

    if regional_submission and regional_form.validate_on_submit():
        user.locale = normalize_locale(regional_form.locale.data)
        user.date_format = normalize_date_format(regional_form.date_format.data)
        user.time_format = normalize_time_format(regional_form.time_format.data)
        db.session.commit()
        operation_feedback = record_operational_activity(
            user_id=user.id,
            event_type='user_preference',
            status='success',
            title='Regional Format Preference Saved',
            message=('Date, time, and locale presentation preferences are now active for this account.'),
            action_url=url_for('settings.general', tab='regional-format'),
            action_label='Open General Settings',
            action_icon='settings-2',
            metadata={
                'preference': 'regional_format',
                'locale': user.locale,
                'date_format': user.date_format,
                'time_format': user.time_format,
            },
            queue_feedback=not bool(request.headers.get('HX-Request')),
            delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
        )
        notification_changed = bool(operation_feedback.get('notification_deck_visible'))
        general_settings_saved = True
        if not request.headers.get('HX-Request'):
            return redirect(url_for('settings.general', tab='regional-format'))

        regional_form = RegionalFormatForm()
        regional_form.locale.data = normalize_locale(user.locale)
        regional_form.date_format.data = normalize_date_format(user.date_format)
        regional_form.time_format.data = normalize_time_format(user.time_format)

    now_utc = datetime.now(UTC)
    current_time_display = format_user_datetime(
        now_utc,
        user.timezone,
        date_format=user.date_format,
        time_format=user.time_format,
        locale=user.locale,
        include_seconds=True,
    )
    context: dict[str, Any] = {
        'active_tab': active_tab,
        'timezone_form': timezone_form,
        'regional_form': regional_form,
        'timezone_choice_groups': timezone_choice_groups(),
        'current_time_display': current_time_display,
        'preview_timestamp': now_utc.isoformat(),
        'system_information': (build_system_information(current_app.config) if can_view_system_information else None),
        'can_view_system_information': can_view_system_information,
        'page_title': 'General Settings',
        'timezone_sync_oob': bool(request.headers.get('HX-Request')),
    }

    template_name = (
        'settings/general/partials/_page_content.html'
        if request.headers.get('HX-Request')
        else 'settings/general/index.html'
    )
    rendered_page = render_template(template_name, **context)
    if request.headers.get('HX-Request') and operation_feedback is not None:
        rendered_page += render_template(
            'components/operational_toast.html',
            **operation_feedback,
            toast_oob=True,
        )
    response = make_response(rendered_page)
    if general_settings_saved:
        trigger_payload: dict[str, Any] = {
            'kaori:general-settings-saved': {'tab': active_tab},
        }
        if notification_changed:
            trigger_payload['kaori:notifications-changed'] = True
        response.headers['HX-Trigger'] = json.dumps(trigger_payload)
    return response


@bp.post('/general/browser-timezone')
@login_required
def sync_browser_timezone():
    user = cast(User, current_user._get_current_object())
    if normalize_timezone_mode(user.timezone_mode) != 'automatic':
        return jsonify({'status': 'ignored', 'timezone': normalize_timezone_name(user.timezone)}), 200

    payload = request.get_json(silent=True) or {}
    browser_timezone = str(payload.get('timezone') or '').strip()
    if not is_valid_timezone_name(browser_timezone):
        return jsonify({'status': 'invalid_timezone'}), 400

    normalized_timezone = normalize_timezone_name(browser_timezone)
    if normalized_timezone == normalize_timezone_name(user.timezone):
        return jsonify({'status': 'unchanged', 'timezone': normalized_timezone}), 200

    user.timezone = normalized_timezone
    db.session.commit()
    return jsonify({'status': 'updated', 'timezone': normalized_timezone}), 200


@bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = cast(User, current_user._get_current_object())
    is_htmx = bool(request.headers.get('HX-Request'))
    active_tab = (request.args.get('tab') or 'profile').strip().lower()
    if active_tab not in {'profile', 'activity', 'credentials'}:
        active_tab = 'profile'

    password_form = ChangePasswordForm()
    auth_source = getattr(user, 'auth_source', 'database') or 'database'
    can_change_password = auth_source == 'database'
    password_feedback: dict[str, str] | None = None
    password_toast: dict[str, Any] | None = None
    notification_changed = False

    if password_form.is_submitted():
        active_tab = 'credentials'
        if not can_change_password:
            password_feedback = {
                'status': 'warning',
                'title': 'Password is managed externally',
                'message': (
                    'This account uses an external authentication source. Password updates must be completed '
                    'in the connected identity provider.'
                ),
            }
        elif password_form.validate():
            current_password = password_form.current_password.data or ''
            new_password = password_form.new_password.data or ''

            if not user.check_password(current_password):
                password_form.current_password.errors = [
                    *password_form.current_password.errors,
                    'Current password is incorrect.',
                ]
                password_feedback = {
                    'status': 'danger',
                    'title': 'Password update failed',
                    'message': 'The current password does not match the active local account password.',
                }
                _record_password_change_rejection(
                    user=user,
                    auth_source=auth_source,
                    reason_code='current_password_mismatch',
                )
            elif user.check_password(new_password):
                password_form.new_password.errors = [
                    *password_form.new_password.errors,
                    'New password must be different from the current password.',
                ]
                password_feedback = {
                    'status': 'danger',
                    'title': 'Password update failed',
                    'message': 'Choose a new Local Database password instead of reusing the active credential.',
                }
                _record_password_change_rejection(
                    user=user,
                    auth_source=auth_source,
                    reason_code='current_password_reuse',
                )
            else:
                user.set_password(new_password)
                db.session.commit()
                preserve_current_session_after_password_change(user)
                password_toast = record_operational_activity(
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
                notification_changed = bool(password_toast.get('notification_deck_visible'))

                if not is_htmx:
                    return redirect(url_for('settings.account', tab='credentials'))

                # Success feedback is delivered once through the shared operational
                # toast and persisted Activity Audit record. Keep the credential
                # workspace free from a duplicate inline success message.
                password_form = ChangePasswordForm()
        else:
            password_feedback = {
                'status': 'danger',
                'title': 'Password update failed',
                'message': 'Review the password requirements and highlighted fields before trying again.',
            }

    identity_context = build_user_identity_context(user)

    recent_login_events = (
        Notification.query.filter(
            Notification.user_id == user.id,
            Notification.event_type == 'authentication',
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(5)
        .all()
    )

    activity_summary = {
        'total': len(recent_login_events),
        'success': 0,
        'failed': 0,
        'sign_out': 0,
    }
    for event in recent_login_events:
        metadata = event.metadata_json or {}
        action = metadata.get('access_action') or ('logout' if event.title == 'User signed out' else 'login')
        if action == 'logout':
            activity_summary['sign_out'] += 1
        elif event.status == 'success':
            activity_summary['success'] += 1
        else:
            activity_summary['failed'] += 1

    context: dict[str, Any] = {
        'active_tab': active_tab,
        'password_form': password_form,
        'can_change_password': can_change_password,
        'password_feedback': password_feedback,
        'password_toast': password_toast,
        'identity_context': identity_context,
        'recent_login_events': recent_login_events,
        'activity_summary': activity_summary,
        'page_title': 'Account & Authentication',
    }
    template_name = 'settings/account/partials/_page_content.html' if is_htmx else 'settings/account/index.html'
    response = make_response(render_template(template_name, **context))
    if notification_changed:
        response.headers['HX-Trigger'] = json.dumps(
            {
                'kaori:notifications-changed': True,
                'kaori:account-password-updated': True,
            }
        )
    return response
