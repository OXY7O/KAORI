from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.auth.forms import ChangePasswordForm
from app.common.timezone import (
    format_datetime,
    normalize_timezone_name,
    timezone_choices,
)
from app.extensions import db
from app.models import AuthLoginEvent, Permission, Role, User
from app.rbac.decorators import permission_required
from app.rbac.service import get_permissions_grouped_by_module, replace_role_permissions, seed_default_rbac
from app.settings.roles.forms import RoleForm

bp = Blueprint(
    'settings',
    __name__,
    url_prefix='/settings',
)

from app.settings.users.routes import register_user_routes

register_user_routes(bp)

@bp.route('/')
@bp.route('/general')
@permission_required('settings.view')
def general():
    return render_template('settings/general/index.html')


@bp.route('/time-locale', methods=['GET', 'POST'])
@login_required
def time_locale():
    user = cast(User, current_user)
    timezone_error = None
    selected_timezone = normalize_timezone_name(user.timezone)

    if request.method == 'POST':
        requested_timezone = (request.form.get('timezone') or '').strip()
        normalized_timezone = normalize_timezone_name(requested_timezone)

        if not requested_timezone or normalized_timezone != requested_timezone:
            timezone_error = 'Choose a valid IANA timezone from the available list.'
            selected_timezone = requested_timezone or selected_timezone
        else:
            user.timezone = normalized_timezone
            db.session.commit()
            flash('Time preference saved.', 'success')
            return redirect(url_for('settings.time_locale'))

    return render_template(
        'settings/time_locale/index.html',
        selected_timezone=selected_timezone,
        timezone_choices=timezone_choices(),
        timezone_error=timezone_error,
        current_time_display=format_datetime(
            datetime.now(UTC),
            selected_timezone,
            '%d %b %Y %H:%M:%S %Z',
        ),
    )


@bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = cast(User, current_user)
    password_form = ChangePasswordForm()
    auth_source = getattr(user, 'auth_source', 'database') or 'database'
    can_change_password = auth_source == 'database'

    password_feedback = None

    if password_form.is_submitted():
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
                return redirect(url_for('settings.account', password_status='updated'))
        else:
            password_feedback = {
                'status': 'danger',
                'title': 'Password update failed',
                'message': 'Review the password requirements and highlighted fields before trying again.',
            }

    if request.args.get('password_status') == 'updated':
        password_feedback = {
            'status': 'success',
            'title': 'Password updated successfully',
            'message': 'Your local database account password has been changed. Use the new password on your next sign-in.',
        }

    recent_login_events = (
        AuthLoginEvent.query.filter(AuthLoginEvent.username == user.username)
        .order_by(AuthLoginEvent.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'settings/account/index.html',
        password_form=password_form,
        can_change_password=can_change_password,
        password_feedback=password_feedback,
        recent_login_events=recent_login_events,
        page_title='Account & Authentication',
    )


@bp.route('/roles')
@permission_required('roles.view')
def roles():
    seed_default_rbac()
    roles_list = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    permissions_by_module = get_permissions_grouped_by_module()
    return render_template('settings/roles/index.html', roles=roles_list, permissions_by_module=permissions_by_module)


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


@bp.route('/system-info')
@permission_required('system.view')
def system_info():
    return render_template('settings/system_info/index.html')
