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
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

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
from app.rbac.notifications import role_access_feedback
from app.rbac.service import (
    expand_permission_ids,
    get_permissions_grouped_by_module,
    get_role_delete_blockers,
    normalize_role_slug,
    replace_role_permissions,
    role_slug_exists,
    seed_default_rbac,
)
from app.settings.general.forms import RegionalFormatForm, TimezonePreferenceForm
from app.settings.roles.forms import DeleteRoleForm, RoleForm
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
    can_view_system_information = user.has_permission('system.view')
    allowed_tabs = {'time-locale', 'regional-format'}
    if can_view_system_information:
        allowed_tabs.add('system-information')
    if active_tab not in allowed_tabs:
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
                password_toast = record_operational_activity(
                    user_id=user.id,
                    event_type='account_security',
                    status='success',
                    title='Account password updated',
                    message='Your KAORI Local Database password was changed successfully.',
                    detail='Use the new password on your next sign-in. The password value was not stored in notification or audit metadata.',
                    action_url=url_for('settings.account', tab='credentials'),
                    action_label='Open Credential Management',
                    action_icon='key-round',
                    metadata={
                        'security_action': 'password_change',
                        'credential_owner': 'KAORI Local Database',
                        'auth_source': auth_source,
                        'result': 'success',
                    },
                    queue_feedback=not is_htmx,
                )
                notification_changed = True

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


@bp.route('/roles')
@permission_required('roles.view')
def roles():
    seed_default_rbac()
    actor = cast(User, current_user._get_current_object())
    roles_list = Role.query.order_by(Role.is_system.desc(), Role.display_name.asc()).all()
    permissions_by_module = get_permissions_grouped_by_module()
    role_assignment_counts = {
        int(role_id): int(count)
        for role_id, count in (
            db.session.query(User.role_id, func.count(User.id))
            .filter(User.role_id.is_not(None), User.deleted_at.is_(None))
            .group_by(User.role_id)
            .all()
        )
    }
    role_delete_blockers = {role.id: get_role_delete_blockers(role) for role in roles_list if not role.is_system}
    return render_template(
        'settings/roles/index.html',
        roles=roles_list,
        permissions_by_module=permissions_by_module,
        can_manage_roles=actor.has_permission('roles.manage'),
        delete_role_form=DeleteRoleForm(),
        role_delete_blockers=role_delete_blockers,
        role_assignment_counts=role_assignment_counts,
        role_permission_keys={role.id: role.permission_keys() for role in roles_list},
        total_permissions=sum(len(items) for items in permissions_by_module.values()),
    )


def _create_custom_role_from_form(
    *,
    form: RoleForm,
    selected_permission_ids: set[int],
    clone_source: Role | None = None,
) -> Role | None:
    slug = normalize_role_slug(form.name.data)
    if len(slug) < 2:
        form.name.errors = [*form.name.errors, 'Role slug must contain at least two letters or numbers.']
        return None
    if role_slug_exists(slug):
        form.name.errors = [*form.name.errors, 'A role with this slug already exists.']
        return None

    role = Role()
    role.name = slug
    role.display_name = (form.display_name.data or slug.replace('_', ' ').title()).strip()
    role.description = (form.description.data or '').strip() or None
    role.is_system = False
    role.is_active = bool(form.is_active.data)
    db.session.add(role)
    db.session.flush()
    effective_permission_ids = replace_role_permissions(role, selected_permission_ids)
    record_admin_event(
        actor=cast(User, current_user),
        action='role.cloned' if clone_source else 'role.created',
        target=role,
        summary=(
            f'Cloned system role {clone_source.display_name} as {role.display_name}.'
            if clone_source
            else f'Created role {role.display_name}.'
        ),
        metadata={
            'role_slug': role.name,
            'source_role_id': clone_source.id if clone_source else None,
            'source_role_slug': clone_source.name if clone_source else None,
            'permission_count': len(effective_permission_ids),
        },
    )
    db.session.commit()
    return role


@bp.route('/roles/new', methods=['GET', 'POST'])
@permission_required('roles.manage')
def new_role():
    seed_default_rbac()
    form = RoleForm()
    if request.method == 'GET':
        form.is_active.data = True

    selected_permission_ids = {int(value) for value in request.form.getlist('permission_ids') if value.isdigit()}
    if form.validate_on_submit():
        role = _create_custom_role_from_form(
            form=form,
            selected_permission_ids=selected_permission_ids,
        )
        if role is not None:
            role_access_feedback(
                actor=cast(User, current_user),
                event_type='rbac_role_created',
                status='success',
                title='Custom role created',
                message=f'{role.display_name} is ready for user assignment.',
                role=role,
            )
            return redirect(url_for('settings.roles'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return render_template(
        'settings/roles/form.html',
        form=form,
        role=None,
        clone_source=None,
        view_only=False,
        permissions_by_module=get_permissions_grouped_by_module(),
        selected_permission_ids=selected_permission_ids,
    )


@bp.route('/roles/<int:role_id>/clone', methods=['GET', 'POST'])
@permission_required('roles.manage')
def clone_role(role_id: int):
    seed_default_rbac()
    source_role = db.session.get(Role, role_id)
    if source_role is None or not source_role.is_system:
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_clone_rejected',
            status='warning',
            title='Role clone blocked',
            message='Only a protected default role can be used as a clone source.',
        )
        return redirect(url_for('settings.roles'))

    form = RoleForm()
    selected_permission_ids = {permission.id for permission in source_role.permissions}
    if request.method == 'GET':
        form.name.data = f'{source_role.name}_custom'
        form.display_name.data = f'{source_role.display_name} Custom'
        form.description.data = f'Custom role cloned from the {source_role.display_name} default baseline.'
        form.is_active.data = True
    else:
        selected_permission_ids = {int(value) for value in request.form.getlist('permission_ids') if value.isdigit()}

    if form.validate_on_submit():
        role = _create_custom_role_from_form(
            form=form,
            selected_permission_ids=selected_permission_ids,
            clone_source=source_role,
        )
        if role is not None:
            role_access_feedback(
                actor=cast(User, current_user),
                event_type='rbac_role_cloned',
                status='success',
                title='Default role cloned',
                message=f'{source_role.display_name} was cloned as {role.display_name}.',
                role=role,
                detail='The cloned role is custom and can now be adjusted independently.',
            )
            return redirect(url_for('settings.roles'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return render_template(
        'settings/roles/form.html',
        form=form,
        role=None,
        clone_source=source_role,
        view_only=False,
        permissions_by_module=get_permissions_grouped_by_module(),
        selected_permission_ids=selected_permission_ids,
    )


@bp.route('/roles/<int:role_id>')
@permission_required('roles.view')
def role_detail(role_id: int):
    seed_default_rbac()
    role = db.session.get(Role, role_id)
    if role is None:
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_unavailable',
            status='error',
            title='Role unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('settings.roles'))

    form = RoleForm(obj=role)
    form.is_active.data = role.is_active
    return render_template(
        'settings/roles/form.html',
        form=form,
        role=role,
        clone_source=None,
        view_only=True,
        permissions_by_module=get_permissions_grouped_by_module(),
        selected_permission_ids={permission.id for permission in role.permissions},
        assigned_user_count=User.query.filter(User.role_id == role.id, User.deleted_at.is_(None)).count(),
    )


@bp.route('/roles/<int:role_id>/edit', methods=['GET', 'POST'])
@permission_required('roles.manage')
def edit_role(role_id: int):
    role = db.session.get(Role, role_id)
    if role is None:
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_update_rejected',
            status='error',
            title='Role update unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('settings.roles'))
    if role.is_system:
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_update_rejected',
            status='warning',
            title='Default role is protected',
            message='Default roles are code-owned and cannot be edited.',
            role=role,
            detail='Clone the default role to create an editable custom variant.',
        )
        return redirect(url_for('settings.role_detail', role_id=role.id))

    form = RoleForm(obj=role)
    selected_permission_ids = {permission.id for permission in role.permissions}
    if request.method == 'GET':
        form.is_active.data = role.is_active
    else:
        selected_permission_ids = {int(value) for value in request.form.getlist('permission_ids') if value.isdigit()}

    if form.validate_on_submit():
        slug = normalize_role_slug(form.name.data)
        if len(slug) < 2:
            form.name.errors = [*form.name.errors, 'Role slug must contain at least two letters or numbers.']
        elif role_slug_exists(slug, exclude_role_id=role.id):
            form.name.errors = [*form.name.errors, 'A role with this slug already exists.']
        else:
            try:
                role.name = slug
                role.display_name = (form.display_name.data or role.display_name).strip()
                role.description = (form.description.data or '').strip() or None
                role.is_active = bool(form.is_active.data)
                effective_permission_ids = replace_role_permissions(role, selected_permission_ids)
                record_admin_event(
                    actor=cast(User, current_user),
                    action='role.updated',
                    target=role,
                    summary=f'Updated role {role.display_name}.',
                    metadata={
                        'role_slug': role.name,
                        'permission_count': len(effective_permission_ids),
                        'is_active': role.is_active,
                    },
                )
                db.session.commit()
            except (SQLAlchemyError, ValueError):
                db.session.rollback()
                current_app.logger.exception(
                    'Failed to update custom role %s with submitted permissions.',
                    role_id,
                )
                role_access_feedback(
                    actor=cast(User, current_user),
                    event_type='rbac_role_update_failed',
                    status='error',
                    title='Custom role update failed',
                    message='No role changes were saved.',
                    role=role,
                    detail='Review the role configuration and permission selection, then try again.',
                )
            else:
                role_access_feedback(
                    actor=cast(User, current_user),
                    event_type='rbac_role_updated',
                    status='success',
                    title='Custom role updated',
                    message=f'{role.display_name} access scope was updated.',
                    role=role,
                    detail=f'{len(effective_permission_ids)} effective permissions are now assigned.',
                )
                return redirect(url_for('settings.roles'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return render_template(
        'settings/roles/form.html',
        form=form,
        role=role,
        clone_source=None,
        view_only=False,
        permissions_by_module=get_permissions_grouped_by_module(),
        selected_permission_ids=selected_permission_ids,
        assigned_user_count=User.query.filter(User.role_id == role.id, User.deleted_at.is_(None)).count(),
    )


@bp.post('/roles/<int:role_id>/delete')
@permission_required('roles.manage')
def delete_role(role_id: int):
    role = db.session.get(Role, role_id)
    if role is None:
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_rejected',
            status='error',
            title='Role deletion unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('settings.roles'))

    form = DeleteRoleForm()
    if not form.validate_on_submit() or str(form.role_id.data) != str(role.id):
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_rejected',
            status='error',
            title='Role deletion rejected',
            message='The role deletion request could not be validated.',
            role=role,
        )
        return redirect(url_for('settings.roles'))
    if role.is_system:
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_rejected',
            status='warning',
            title='Default role is protected',
            message='Default roles cannot be deleted.',
            role=role,
        )
        return redirect(url_for('settings.roles'))

    blockers = get_role_delete_blockers(role)
    if blockers['assigned_users'] or blockers['identity_providers']:
        blocker_parts = []
        if blockers['assigned_users']:
            blocker_parts.append(f'{blockers["assigned_users"]} user assignment(s)')
        if blockers['identity_providers']:
            blocker_parts.append(f'{blockers["identity_providers"]} identity provider default mapping(s)')
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_blocked',
            status='warning',
            title='Role deletion blocked',
            message='The custom role is still referenced by ' + ' and '.join(blocker_parts) + '.',
            role=role,
            detail='Remove the user and identity-provider mappings before deleting this role.',
        )
        return redirect(url_for('settings.roles'))

    role_name = role.display_name
    role_snapshot = {
        'target_type': 'role',
        'target_id': role.id,
        'role_slug': role.name,
        'role_display_name': role.display_name,
        'role_type': 'custom',
        'lifecycle_status': 'deleted',
        'permission_count': len(role.permissions),
    }
    record_admin_event(
        actor=cast(User, current_user),
        action='role.deleted',
        target=role,
        summary=f'Deleted custom role {role_name}.',
        metadata={'role_slug': role.name},
    )
    db.session.delete(role)
    db.session.commit()
    role_access_feedback(
        actor=cast(User, current_user),
        event_type='rbac_role_deleted',
        status='success',
        title='Custom role deleted',
        message=f'{role_name} was removed from the role registry.',
        role_snapshot=role_snapshot,
        detail='Historical administrative records remain available in Activity Audit Log.',
    )
    return redirect(url_for('settings.roles'))


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
