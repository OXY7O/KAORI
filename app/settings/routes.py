from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.auth.forms import ChangePasswordForm
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
from app.extensions import db
from app.models import Notification, Permission, Role, User
from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required
from app.rbac.service import (
    get_permissions_grouped_by_module,
    replace_role_permissions,
    seed_default_rbac,
)
from app.settings.general.forms import RegionalFormatForm, TimezonePreferenceForm
from app.settings.roles.forms import RoleForm
from app.settings.system_information import build_system_information
from app.users.service import build_user_identity_context, record_admin_event

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
    active_tab = (request.args.get('tab') or 'time-locale').strip().lower()
    if active_tab not in {'time-locale', 'regional-format', 'system-information'}:
        active_tab = 'time-locale'

    timezone_form = TimezonePreferenceForm()
    regional_form = RegionalFormatForm()
    notification_changed = False

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
            record_operational_activity(
                user_id=user.id,
                event_type='user_preference',
                status='success',
                title='Time zone preference saved',
                message=(f'KAORI now renders time-related information for this account using {user.timezone}.'),
                action_url=url_for('settings.general', tab='time-locale'),
                action_label='Open General Settings',
                action_icon='settings-2',
                metadata={
                    'preference': 'timezone',
                    'timezone_mode': user.timezone_mode,
                    'timezone': user.timezone,
                },
            )
            notification_changed = True
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
        record_operational_activity(
            user_id=user.id,
            event_type='user_preference',
            status='success',
            title='Regional format preference saved',
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
        )
        notification_changed = True
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
        'system_information': build_system_information(current_app.config),
        'page_title': 'General Settings',
        'timezone_sync_oob': bool(request.headers.get('HX-Request')),
    }

    template_name = (
        'settings/general/partials/_page_content.html'
        if request.headers.get('HX-Request')
        else 'settings/general/index.html'
    )
    response = make_response(render_template(template_name, **context))
    if notification_changed:
        response.headers['HX-Trigger'] = json.dumps(
            {
                'kaori:notifications-changed': True,
                'kaori:general-settings-saved': {'tab': active_tab},
            }
        )
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
    active_tab = (request.args.get('tab') or 'profile').strip().lower()
    if active_tab not in {'profile', 'activity', 'credentials'}:
        active_tab = 'profile'

    password_form = ChangePasswordForm()
    auth_source = getattr(user, 'auth_source', 'database') or 'database'
    can_change_password = auth_source == 'database'
    password_feedback = None

    if password_form.is_submitted():
        active_tab = 'credentials'
        if not can_change_password:
            password_feedback = {
                'status': 'warning',
                'title': 'Password is managed externally',
                'message': 'This account uses an external authentication source. Password updates must be completed in the connected identity provider.',
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
            else:
                user.set_password(new_password)
                db.session.commit()
                return redirect(
                    url_for(
                        'settings.account',
                        tab='credentials',
                        password_status='updated',
                    )
                )
        else:
            password_feedback = {
                'status': 'danger',
                'title': 'Password update failed',
                'message': 'Review the password requirements and highlighted fields before trying again.',
            }

    if request.args.get('password_status') == 'updated':
        active_tab = 'credentials'
        password_feedback = {
            'status': 'success',
            'title': 'Password updated successfully',
            'message': 'Your local database account password has been changed. Use the new password on your next sign-in.',
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

    return render_template(
        'settings/account/index.html',
        active_tab=active_tab,
        password_form=password_form,
        can_change_password=can_change_password,
        password_feedback=password_feedback,
        identity_context=identity_context,
        recent_login_events=recent_login_events,
        activity_summary=activity_summary,
        page_title='Account & Authentication',
    )


@bp.route('/roles')
@permission_required('roles.view')
def roles():
    seed_default_rbac()
    roles_list = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    permissions_by_module = get_permissions_grouped_by_module()
    return render_template(
        'settings/roles/index.html',
        roles=roles_list,
        permissions_by_module=permissions_by_module,
    )


@bp.route('/roles/new', methods=['GET', 'POST'])
@permission_required('roles.manage')
def new_role():
    seed_default_rbac()
    form = RoleForm()
    form.is_active.data = True if request.method == 'GET' else form.is_active.data
    permissions = Permission.query.order_by(Permission.module.asc(), Permission.key.asc()).all()

    if form.validate_on_submit():
        role = Role()
        role.name = (form.name.data or '').strip().lower().replace(' ', '_')
        role.display_name = form.display_name.data or role.name.title()
        role.description = form.description.data
        role.is_system = False
        role.is_active = bool(form.is_active.data)
        db.session.add(role)
        db.session.flush()
        selected_permission_ids = [int(value) for value in request.form.getlist('permission_ids')]
        replace_role_permissions(role, selected_permission_ids)
        record_admin_event(
            actor=cast(User, current_user),
            action='role.created',
            target=role,
            summary=f'Created role {role.display_name}.',
        )
        db.session.commit()
        flash('Custom role created successfully.', 'success')
        return redirect(url_for('settings.roles'))

    return render_template(
        'settings/roles/form.html',
        form=form,
        role=None,
        permissions=permissions,
        permissions_by_module=get_permissions_grouped_by_module(),
        selected_permission_ids=set(),
    )


@bp.route('/roles/<int:role_id>/edit', methods=['GET', 'POST'])
@permission_required('roles.manage')
def edit_role(role_id: int):
    role = db.session.get(Role, role_id)
    if role is None:
        flash('Role not found.', 'danger')
        return redirect(url_for('settings.roles'))

    form = RoleForm(obj=role)
    permissions = Permission.query.order_by(Permission.module.asc(), Permission.key.asc()).all()
    selected_permission_ids = {permission.id for permission in role.permissions}

    if request.method == 'GET':
        form.is_active.data = role.is_active

    if form.validate_on_submit():
        role.display_name = form.display_name.data or role.display_name
        role.description = form.description.data
        role.is_active = bool(form.is_active.data)
        if not role.is_system:
            role.name = (form.name.data or role.name).strip().lower().replace(' ', '_')
            selected_permission_ids = {int(value) for value in request.form.getlist('permission_ids')}
            replace_role_permissions(role, selected_permission_ids)
        record_admin_event(
            actor=cast(User, current_user),
            action='role.updated',
            target=role,
            summary=f'Updated role {role.display_name}.',
        )
        db.session.commit()
        flash('Role updated successfully.', 'success')
        return redirect(url_for('settings.roles'))

    return render_template(
        'settings/roles/form.html',
        form=form,
        role=role,
        permissions=permissions,
        permissions_by_module=get_permissions_grouped_by_module(),
        selected_permission_ids=selected_permission_ids,
    )


@bp.route('/permissions')
@permission_required('roles.view')
def permission_catalog():
    seed_default_rbac()
    permissions_by_module = get_permissions_grouped_by_module()
    roles_list = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    permissions = Permission.query.order_by(
        Permission.module.asc(), Permission.action.asc(), Permission.key.asc()
    ).all()
    assignment_count = sum(len(permission.role_permissions) for permission in permissions)

    return render_template(
        'settings/permissions/index.html',
        permissions=permissions,
        permissions_by_module=permissions_by_module,
        roles=roles_list,
        total_permissions=len(permissions),
        total_modules=len(permissions_by_module),
        assignment_count=assignment_count,
    )


@bp.route('/reports')
@permission_required('settings.manage_integrations')
def reports():
    return render_template('settings/reports/index.html')
