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

from app.access.authentication.forms import ChangePasswordForm
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
from app.settings.account.actions import process_password_change
from app.settings.account.queries import authentication_activity_summary, recent_authentication_events
from app.settings.general.actions import (
    save_regional_format_preference,
    save_timezone_preference,
    sync_browser_timezone_preference,
)
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
        'system_information': build_system_information(current_app.config) if can_view_system_information else None,
        'can_view_system_information': can_view_system_information,
        'page_title': 'General Settings',
        'timezone_sync_oob': is_htmx,
    }
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
    user = cast(User, current_user._get_current_object())
    payload = request.get_json(silent=True) or {}
    browser_timezone = str(payload.get('timezone') or '').strip()
    status, timezone = sync_browser_timezone_preference(user=user, browser_timezone=browser_timezone)
    return jsonify({'status': status, 'timezone': timezone}), 400 if status == 'invalid_timezone' else 200


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

    identity_context = build_user_identity_context(user)
    recent_login_events = recent_authentication_events(user.id)
    activity_summary = authentication_activity_summary(recent_login_events)

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
