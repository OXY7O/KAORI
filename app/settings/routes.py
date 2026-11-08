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
from flask_login import current_user, login_fresh, login_required
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.authentication.forms import ChangePasswordForm
from app.access.authentication.mfa.qr import build_totp_qr_data_uri
from app.access.authentication.mfa.service import (
    MfaVerificationError,
    begin_mfa_enrollment,
    confirm_mfa_enrollment,
    mfa_enrolled,
    mfa_policy_mode,
    regenerate_mfa_recovery_codes,
    verify_mfa_challenge,
)
from app.access.users.directory import build_user_identity_context
from app.common.timezone import (
    format_user_datetime,
    normalize_date_format,
    normalize_locale,
    normalize_time_format,
    normalize_timezone_mode,
    normalize_timezone_name,
    timezone_choice_groups,
)
from app.models import User
from app.platform_operations.notifications.feedback import (
    OperationalDeliveryPolicy,
    OperationalFeedbackSpec,
    build_operational_feedback,
    queue_operational_feedback,
)
from app.platform_operations.notifications.service import create_transient_feedback
from app.security.credentials import CredentialEncryptionError
from app.settings.account.actions import process_password_change
from app.settings.account.queries import (
    account_mfa_factor,
    authentication_activity_summary,
    recent_authentication_events,
)
from app.settings.general.actions import (
    save_regional_format_preference,
    save_timezone_preference,
    sync_browser_timezone_preference,
)
from app.settings.general.compatibility_registry import build_compatibility_registry
from app.settings.general.forms import RegionalFormatForm, TimezonePreferenceForm
from app.settings.system_information import build_system_information

bp = Blueprint(
    'settings',
    __name__,
    url_prefix='/settings',
)


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/general', methods=['GET', 'POST'])
@login_required
def general():
    user = cast(User, current_user._get_current_object())
    is_htmx = bool(request.headers.get('HX-Request'))
    active_tab = (request.args.get('tab') or 'time-locale').strip().lower()
    can_view_system_information = user.has_permission('system.view')
    allowed_tabs = {'time-locale', 'regional-format'}
    if can_view_system_information:
        allowed_tabs.update({'system-information', 'compatibility-versions'})
    if active_tab not in allowed_tabs:
        active_tab = 'time-locale'

    timezone_form = TimezonePreferenceForm()
    regional_form = RegionalFormatForm()
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

    operation_feedback: dict[str, Any] | None = None
    general_settings_saved = False
    notification_changed = False
    if timezone_submission:
        result = save_timezone_preference(user=user, form=timezone_form, is_htmx=is_htmx)
        operation_feedback = result.feedback
        general_settings_saved = result.saved
        notification_changed = result.notification_changed
        if result.saved and not is_htmx:
            return redirect(url_for('settings.general', tab='time-locale'))
        if result.saved:
            timezone_form = TimezonePreferenceForm()
            timezone_form.timezone_mode.data = normalize_timezone_mode(user.timezone_mode)
            timezone_form.timezone.data = normalize_timezone_name(user.timezone)
    elif regional_submission:
        result = save_regional_format_preference(user=user, form=regional_form, is_htmx=is_htmx)
        operation_feedback = result.feedback
        general_settings_saved = result.saved
        notification_changed = result.notification_changed
        if result.saved and not is_htmx:
            return redirect(url_for('settings.general', tab='regional-format'))
        if result.saved:
            regional_form = RegionalFormatForm()
            regional_form.locale.data = normalize_locale(user.locale)
            regional_form.date_format.data = normalize_date_format(user.date_format)
            regional_form.time_format.data = normalize_time_format(user.time_format)

    system_information = build_system_information(current_app.config) if can_view_system_information else None
    compatibility_registry = None
    if active_tab == 'compatibility-versions' and system_information is not None:
        compatibility_registry = build_compatibility_registry(
            system_information['compatibility_products'],
            search=request.args.get('compatibility_search'),
            support=request.args.get('compatibility_support'),
            page=request.args.get('compatibility_page'),
            selected_key=request.args.get('compatibility_key'),
            profile_page=request.args.get('compatibility_profile_page'),
        )

    now_utc = datetime.now(UTC)
    context: dict[str, Any] = {
        'active_tab': active_tab,
        'timezone_form': timezone_form,
        'regional_form': regional_form,
        'timezone_choice_groups': timezone_choice_groups(),
        'current_time_display': format_user_datetime(
            now_utc,
            user.timezone,
            date_format=user.date_format,
            time_format=user.time_format,
            locale=user.locale,
            include_seconds=True,
        ),
        'preview_timestamp': now_utc.isoformat(),
        'system_information': system_information,
        'compatibility_registry': compatibility_registry,
        'can_view_system_information': can_view_system_information,
        'page_title': 'General Settings',
        'timezone_sync_oob': is_htmx,
    }
    if (
        request.method == 'GET'
        and is_htmx
        and active_tab == 'compatibility-versions'
        and compatibility_registry is not None
        and request.headers.get('HX-Target') == 'compatibility-registry'
    ):
        return make_response(render_template('settings/general/partials/_compatibility_registry.html', **context))
    if (
        request.method == 'GET'
        and is_htmx
        and active_tab == 'compatibility-versions'
        and compatibility_registry is not None
        and request.headers.get('HX-Target') == 'compatibility-registry-results'
    ):
        return make_response(
            render_template('settings/general/partials/_compatibility_registry_results.html', **context)
        )

    template_name = 'settings/general/partials/_page_content.html' if is_htmx else 'settings/general/index.html'
    rendered_page = render_template(template_name, **context)
    if is_htmx and operation_feedback is not None:
        rendered_page += render_template('components/operational_toast.html', **operation_feedback, toast_oob=True)
    response = make_response(rendered_page)
    if general_settings_saved:
        trigger_payload: dict[str, Any] = {'kaori:general-settings-saved': {'tab': active_tab}}
        if notification_changed:
            trigger_payload['kaori:notifications-changed'] = True
        response.headers['HX-Trigger'] = json.dumps(trigger_payload)
    return response


@bp.post('/general/browser-timezone')
@login_required
def sync_browser_timezone():
    # The browser includes a session-bound Flask-WTF token for this JSON mutation.
    # The preference forms' CSRF validation does not cover a standalone POST.
    try:
        validate_csrf(request.headers.get('X-CSRFToken'))
    except ValidationError:
        return jsonify({'status': 'invalid_csrf'}), 400

    user = cast(User, current_user._get_current_object())
    payload = request.get_json(silent=True) or {}
    browser_timezone = str(payload.get('timezone') or '').strip()
    status, timezone = sync_browser_timezone_preference(user=user, browser_timezone=browser_timezone)
    return jsonify({'status': status, 'timezone': timezone}), 400 if status == 'invalid_timezone' else 200


def _mfa_account_error_message(error: MfaVerificationError) -> str:
    """Translate known MFA failures into safe actionable account guidance."""
    return {
        'Sign in again before changing MFA.': (
            'Your sign-in session is no longer fresh. Sign out and sign back in before trying again.'
        ),
        'Your current password was not accepted.': (
            'Current password was not accepted. Verify your password and try again.'
        ),
        'MFA is already enrolled.': 'MFA is already enrolled. Use the recovery section below.',
        'Start MFA enrollment again.': 'Generate a new setup key before verifying a code.',
        'MFA enrollment expired; start again.': 'Setup key expired. Generate a new setup key and retry.',
        'Verification code was not accepted.': (
            'Verification code was not accepted. Check your authenticator time and retry.'
        ),
    }.get(str(error), 'MFA request was not accepted. Verify your session and retry.')


def _process_account_mfa_action(
    user: User, *, is_htmx: bool
) -> tuple[str | None, str | None, list[str] | None, dict[str, Any] | None]:
    """Process a fresh-session MFA mutation and preserve its feedback semantics."""
    mfa_setup_secret: str | None = None
    mfa_setup_qr_src: str | None = None
    mfa_recovery_codes: list[str] | None = None
    mfa_toast: dict[str, Any] | None = None
    action = str(request.form.get('mfa_action') or '')
    status = 'error'
    title = 'MFA request not accepted'
    message = 'Verify your sign-in session and retry.'
    committed_audit = False
    try:
        validate_csrf(request.form.get('csrf_token'))
        if not login_fresh():
            raise MfaVerificationError('Sign in again before changing MFA.')
        if action in {'begin', 'regenerate'} and user.auth_source == 'database':
            password = str(request.form.get('current_password') or '')
            if not password or not user.check_password(password):
                raise MfaVerificationError('Your current password was not accepted.')
        if action == 'begin':
            mfa_setup_secret = begin_mfa_enrollment(user)
            # QR contains the same one-time setup secret. Never persist it
            # or send it to a third-party QR endpoint.
            mfa_setup_qr_src = build_totp_qr_data_uri(mfa_setup_secret, account_label=user.username)
            title = 'Authenticator setup started'
            message = 'Scan the QR code or enter the setup key, then verify one code.'
        elif action == 'confirm':
            mfa_recovery_codes = confirm_mfa_enrollment(user, str(request.form.get('verification_code') or ''))
            title = 'MFA enabled'
            message = 'Save the recovery codes now. They will not be shown again.'
        elif action == 'regenerate':
            verify_mfa_challenge(user, str(request.form.get('verification_code') or ''), authenticated=True)
            mfa_recovery_codes = regenerate_mfa_recovery_codes(user)
            title = 'Recovery codes regenerated'
            message = 'Save the new codes now. Previously unused codes are invalid.'
        else:
            raise MfaVerificationError('Unsupported MFA operation.')
        status = 'success'
        # The factor service already staged and committed the Activity
        # Audit event. This toast must not generate another audit record.
        committed_audit = True
    except ValidationError:
        title = 'MFA form expired'
        message = 'Refresh this page and submit again.'
    except MfaVerificationError as exc:
        title = 'MFA request not accepted'
        message = _mfa_account_error_message(exc)
    except (CredentialEncryptionError, SQLAlchemyError):
        title = 'MFA temporarily unavailable'
        message = 'MFA configuration is temporarily unavailable.'
        current_app.logger.warning('MFA self-service persistence unavailable.', exc_info=True)

    if committed_audit:
        mfa_toast = build_operational_feedback(
            OperationalFeedbackSpec(
                status=status,
                title=title,
                message=message,
                activity_audit_saved=True,
                notification_deck_visible=False,
                delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
            )
        )
    else:
        mfa_toast = create_transient_feedback(status=status, title=title, message=message)
    if not is_htmx:
        queue_operational_feedback(mfa_toast)

    return mfa_setup_secret, mfa_setup_qr_src, mfa_recovery_codes, mfa_toast


@bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = cast(User, current_user._get_current_object())
    is_htmx = bool(request.headers.get('HX-Request'))
    active_tab = (request.args.get('tab') or 'profile').strip().lower()
    if active_tab not in {'profile', 'activity', 'credentials', 'mfa'}:
        active_tab = 'profile'

    password_form = ChangePasswordForm()
    auth_source = getattr(user, 'auth_source', 'database') or 'database'
    can_change_password = auth_source == 'database'
    password_feedback: dict[str, str] | None = None
    password_toast: dict[str, Any] | None = None
    notification_changed = False
    if password_form.is_submitted() and active_tab != 'mfa':
        active_tab = 'credentials'
        result = process_password_change(
            user=user,
            form=password_form,
            auth_source=auth_source,
            is_htmx=is_htmx,
        )
        password_form = result.form
        password_feedback = result.inline_feedback
        password_toast = result.toast
        notification_changed = result.notification_changed
        if result.saved and not is_htmx:
            return redirect(url_for('settings.account', tab='credentials'))

    mfa_setup_secret: str | None = None
    mfa_setup_qr_src: str | None = None
    mfa_recovery_codes: list[str] | None = None
    mfa_toast: dict[str, Any] | None = None
    if active_tab == 'mfa' and request.method == 'POST':
        mfa_setup_secret, mfa_setup_qr_src, mfa_recovery_codes, mfa_toast = _process_account_mfa_action(
            user, is_htmx=is_htmx
        )

    mfa_factor = account_mfa_factor(user.id)
    mfa_state = {
        'enrolled': mfa_enrolled(user.id),
        'enrollment_pending': bool(mfa_factor is not None and not mfa_factor.enabled),
        'policy_mode': mfa_policy_mode(),
        'recovery_count': len(mfa_factor.recovery_hashes or []) if mfa_factor is not None and mfa_factor.enabled else 0,
    }

    identity_context = build_user_identity_context(user)
    recent_login_events = recent_authentication_events(user.id)
    activity_summary = authentication_activity_summary(recent_login_events)

    context: dict[str, Any] = {
        'active_tab': active_tab,
        'password_form': password_form,
        'can_change_password': can_change_password,
        'password_feedback': password_feedback,
        'password_toast': password_toast,
        'mfa_state': mfa_state,
        'mfa_setup_secret': mfa_setup_secret,
        'mfa_setup_qr_src': mfa_setup_qr_src,
        'mfa_toast': mfa_toast if is_htmx else None,
        'mfa_recovery_codes': mfa_recovery_codes,
        'identity_context': identity_context,
        'recent_login_events': recent_login_events,
        'activity_summary': activity_summary,
        'page_title': 'Account & Authentication',
    }
    template_name = 'settings/account/partials/_page_content.html' if is_htmx else 'settings/account/index.html'
    response = make_response(render_template(template_name, **context))
    if mfa_setup_secret is not None or mfa_recovery_codes is not None:
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Referrer-Policy'] = 'no-referrer'
    if notification_changed:
        response.headers['HX-Trigger'] = json.dumps(
            {
                'kaori:notifications-changed': True,
                'kaori:account-password-updated': True,
            }
        )
    return response
