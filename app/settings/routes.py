from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from typing import Any, cast

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
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
from app.settings.users.forms import ResetPasswordForm, UserForm
from app.settings.users.service import (
    assign_user_form_choices,
    build_users_payload,
    can_activate_user,
    can_create_user,
    can_deactivate_user,
    can_delete_user,
    can_edit_user,
    can_reset_user_password,
    create_or_update_user,
    normalize_user_filters,
    record_admin_event,
    set_user_active,
    soft_delete_user,
)

bp = Blueprint(
    'settings',
    __name__,
    url_prefix='/settings',
)

LOGIN_ACTIVITY_PER_PAGE_OPTIONS = [5, 10, 25, 50]
LOGIN_ACTIVITY_DEFAULT_PER_PAGE = 5
LOGIN_ACTIVITY_MAX_RECORDS = 100
LOGIN_ACTIVITY_STATUS_OPTIONS = ['all', 'success', 'failed']


def _normalize_status(value: str | None) -> str:
    selected_status = (value or 'all').strip().lower()

    if selected_status not in LOGIN_ACTIVITY_STATUS_OPTIONS:
        return 'all'

    return selected_status


def _normalize_per_page(value: str | None) -> int:
    try:
        per_page = int(value or LOGIN_ACTIVITY_DEFAULT_PER_PAGE)
    except ValueError:
        return LOGIN_ACTIVITY_DEFAULT_PER_PAGE

    if per_page not in LOGIN_ACTIVITY_PER_PAGE_OPTIONS:
        return LOGIN_ACTIVITY_DEFAULT_PER_PAGE

    return per_page


def _normalize_page(value: str | None) -> int:
    try:
        page = int(value or 1)
    except ValueError:
        return 1

    return max(page, 1)


def _build_pagination(*, page: int, per_page: int, total_items: int) -> dict[str, Any]:
    total_pages = max(ceil(total_items / per_page), 1)
    current_page = min(max(page, 1), total_pages)

    if total_items:
        start_item = ((current_page - 1) * per_page) + 1
        end_item = min(current_page * per_page, total_items)
    else:
        start_item = 0
        end_item = 0

    return {
        'page': current_page,
        'per_page': per_page,
        'total_items': total_items,
        'total_pages': total_pages,
        'start_item': start_item,
        'end_item': end_item,
        'has_prev': current_page > 1,
        'has_next': current_page < total_pages,
        'prev_page': max(current_page - 1, 1),
        'next_page': min(current_page + 1, total_pages),
    }


def _redirect_to_users() -> Any:
    if request.headers.get('HX-Request'):
        return _render_users_content()

    return redirect(url_for('settings.users'))


def _render_users_content() -> Any:
    filters = normalize_user_filters(request.values.to_dict())
    payload = build_users_payload(filters, actor=cast(User, current_user))
    return render_template('settings/users/partials/_content.html', **payload)


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


@bp.route('/users')
@permission_required('users.view')
def users():
    filters = normalize_user_filters(request.args.to_dict())
    payload = build_users_payload(filters, actor=cast(User, current_user))
    template_name = (
        'settings/users/partials/_content.html' if request.headers.get('HX-Request') else 'settings/users/index.html'
    )
    return render_template(template_name, **payload)


@bp.route('/users/new', methods=['GET', 'POST'])
@permission_required('users.manage')
def new_user():
    seed_default_rbac()
    form = UserForm()
    assign_user_form_choices(form, include_admin_roles=cast(User, current_user).is_super_admin)
    form.is_active.data = True if request.method == 'GET' else form.is_active.data

    if form.validate_on_submit():
        allowed, message = can_create_user(
            cast(User, current_user),
            requested_role_id=form.role_id.data,
            requested_is_super_admin=bool(form.is_super_admin.data),
        )
        user = create_or_update_user(form) if allowed else None
        if not allowed:
            flash(message or 'This account cannot be created.', 'warning')
        elif user is None:
            flash('The user account could not be prepared.', 'danger')
        elif user.auth_source == 'database' and not form.password.data:
            form.password.errors = [
                *form.password.errors,
                'Password is required for database-managed users.',
            ]
        else:
            try:
                db.session.flush()
                record_admin_event(
                    actor=cast(User, current_user),
                    action='user.created',
                    target=user,
                    summary=f'Created user {user.username}.',
                    metadata={'auth_source': user.auth_source, 'role': user.role_name},
                )
                db.session.commit()
                flash('User created successfully.', 'success')
                return _redirect_to_users()
            except IntegrityError:
                db.session.rollback()
                flash('Username or email already exists.', 'danger')

    return render_template(
        'settings/users/form.html',
        form=form,
        mode='create',
        user=None,
        can_manage_admin_fields=cast(User, current_user).is_super_admin,
    )


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@permission_required('users.manage')
def edit_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash('User not found.', 'danger')
        return _redirect_to_users()

    actor = cast(User, current_user)
    allowed, message = can_edit_user(
        actor,
        user,
        requested_role_id=user.role_id,
        requested_is_active=user.account_is_active,
        requested_is_super_admin=user.is_super_admin,
    )
    if not allowed:
        flash(message or 'This account cannot be edited.', 'warning')
        return _redirect_to_users()

    form = UserForm(obj=user)
    assign_user_form_choices(form, include_admin_roles=actor.is_super_admin)

    if request.method == 'GET':
        form.role_id.data = user.role_id or (user.role_record.id if user.role_record else 0)
        form.is_active.data = user.account_is_active
        form.is_super_admin.data = user.is_super_admin

    if form.validate_on_submit():
        allowed, message = can_edit_user(
            cast(User, current_user),
            user,
            requested_role_id=form.role_id.data,
            requested_is_active=bool(form.is_active.data),
            requested_is_super_admin=bool(form.is_super_admin.data),
        )
        if not allowed:
            flash(message or 'This account cannot be modified.', 'warning')
        else:
            try:
                create_or_update_user(form, user)
                record_admin_event(
                    actor=cast(User, current_user),
                    action='user.updated',
                    target=user,
                    summary=f'Updated user {user.username}.',
                    metadata={'auth_source': user.auth_source, 'role': user.role_name},
                )
                db.session.commit()
                flash('User updated successfully.', 'success')
                return _redirect_to_users()
            except IntegrityError:
                db.session.rollback()
                flash('Username or email already exists.', 'danger')

    return render_template(
        'settings/users/form.html',
        form=form,
        mode='edit',
        user=user,
        can_manage_admin_fields=cast(User, current_user).is_super_admin,
    )


@bp.route('/users/<int:user_id>/activate', methods=['POST'])
@permission_required('users.activate')
def activate_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash('User not found.', 'danger')
        return _redirect_to_users()

    allowed, message = can_activate_user(cast(User, current_user), user)
    if not allowed:
        flash(message or 'This account cannot be activated from here.', 'warning')
        return _redirect_to_users()

    set_user_active(user, True)
    record_admin_event(
        actor=cast(User, current_user), action='user.activated', target=user, summary=f'Activated user {user.username}.'
    )
    db.session.commit()
    flash('User activated successfully.', 'success')
    return _redirect_to_users()


@bp.route('/users/<int:user_id>/deactivate', methods=['POST'])
@permission_required('users.activate')
def deactivate_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash('User not found.', 'danger')
        return _redirect_to_users()

    allowed, message = can_deactivate_user(cast(User, current_user), user)
    if not allowed:
        flash(message or 'This account cannot be deactivated from here.', 'warning')
        return _redirect_to_users()

    set_user_active(user, False)
    record_admin_event(
        actor=cast(User, current_user),
        action='user.deactivated',
        target=user,
        summary=f'Deactivated user {user.username}.',
    )
    db.session.commit()
    flash('User deactivated successfully.', 'success')
    return _redirect_to_users()


@bp.route('/users/<int:user_id>/reset-password', methods=['GET', 'POST'])
@permission_required('users.reset_password')
def reset_user_password(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash('User not found.', 'danger')
        return _redirect_to_users()

    allowed, message = can_reset_user_password(cast(User, current_user), user)
    if not allowed:
        flash(message or 'Password reset is not allowed for this account.', 'warning')
        return _redirect_to_users()

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data or '')
        record_admin_event(
            actor=cast(User, current_user),
            action='user.password_reset',
            target=user,
            summary=f'Reset password for user {user.username}.',
        )
        db.session.commit()
        flash('Password reset successfully.', 'success')
        return _redirect_to_users()

    return render_template('settings/users/reset_password.html', form=form, user=user)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@permission_required('users.delete')
def delete_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash('User not found.', 'danger')
        return _redirect_to_users()

    allowed, message = can_delete_user(cast(User, current_user), user)
    if not allowed:
        flash(message or 'This account cannot be deleted from here.', 'warning')
        return _redirect_to_users()

    soft_delete_user(user)
    record_admin_event(
        actor=cast(User, current_user),
        action='user.deleted',
        target=user,
        summary=f'Soft deleted user {user.username}.',
    )
    db.session.commit()
    flash('User soft deleted successfully.', 'success')
    return _redirect_to_users()


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


@bp.route('/login-activity')
@permission_required('settings.view_login_activity')
def login_activity():
    selected_page = _normalize_page(request.args.get('page'))
    selected_per_page = _normalize_per_page(request.args.get('per_page'))
    selected_status = _normalize_status(request.args.get('status'))

    events_query = AuthLoginEvent.query

    if selected_status == 'success':
        events_query = events_query.filter(AuthLoginEvent.success.is_(True))
    elif selected_status == 'failed':
        events_query = events_query.filter(AuthLoginEvent.success.is_(False))

    matching_attempts_all = events_query.count()
    total_attempts = min(matching_attempts_all, LOGIN_ACTIVITY_MAX_RECORDS)
    pagination = _build_pagination(
        page=selected_page,
        per_page=selected_per_page,
        total_items=total_attempts,
    )

    recent_events = (
        events_query.order_by(AuthLoginEvent.created_at.desc())
        .offset((pagination['page'] - 1) * selected_per_page)
        .limit(selected_per_page)
        .all()
    )
    total_attempts_all = AuthLoginEvent.query.count()
    successful_logins = AuthLoginEvent.query.filter_by(success=True).count()
    failed_logins = AuthLoginEvent.query.filter_by(success=False).count()

    template_name = (
        'settings/login_activity/partials/_events_table.html'
        if request.headers.get('HX-Request')
        else 'settings/login_activity/index.html'
    )

    return render_template(
        template_name,
        recent_events=recent_events,
        total_attempts=total_attempts_all,
        displayed_total_attempts=total_attempts,
        matching_attempts=matching_attempts_all,
        successful_logins=successful_logins,
        failed_logins=failed_logins,
        pagination=pagination,
        per_page_options=LOGIN_ACTIVITY_PER_PAGE_OPTIONS,
        selected_per_page=selected_per_page,
        selected_status=selected_status,
        status_options=LOGIN_ACTIVITY_STATUS_OPTIONS,
        max_login_activity_records=LOGIN_ACTIVITY_MAX_RECORDS,
        login_audit_retention_days=current_app.config.get('AUTH_LOGIN_AUDIT_RETENTION_DAYS', 90),
    )


@bp.route('/reports')
@permission_required('settings.manage_integrations')
def reports():
    return render_template('settings/reports/index.html')


@bp.route('/system-info')
@permission_required('system.view')
def system_info():
    return render_template('settings/system_info/index.html')
