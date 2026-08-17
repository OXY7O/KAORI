from __future__ import annotations

from typing import Any, cast

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.common.admin_audit import record_admin_event
from app.extensions.db import db
from app.models import User
from app.rbac.decorators import permission_required
from app.users.directory import (
    build_user_identity_context,
    build_users_payload,
    normalize_user_filters,
)
from app.users.forms import ResetPasswordForm, UserForm
from app.users.notifications import user_management_feedback
from app.users.service import (
    assign_user_form_choices,
    can_activate_user,
    can_create_user,
    can_deactivate_user,
    can_delete_user,
    can_edit_user,
    can_reset_user_password,
    can_restore_user,
    create_or_update_user,
    lock_active_super_admin_boundary,
    restore_user,
    set_user_active,
    soft_delete_user,
)

bp = Blueprint('users', __name__, url_prefix='/users')


def render_users_content(feedback: dict[str, Any] | None = None) -> str:
    filters = normalize_user_filters(request.values.to_dict())
    payload = build_users_payload(filters, actor=cast(User, current_user))
    content = render_template('users/partials/_content.html', **payload)
    if feedback is None:
        return content
    hero = render_template('users/partials/_hero.html', **payload, hero_oob=True)
    toast = render_template(
        'components/operational_toast.html',
        **feedback,
        toast_oob=True,
    )
    return f'{content}{hero}{toast}'


def finish(feedback: dict[str, Any]) -> Any:
    if request.headers.get('HX-Request') == 'true':
        return render_users_content(feedback)
    return redirect(url_for('users.index'))


def reject(title: str, message: str, *, status: str = 'warning', target: User | None = None) -> Any:
    feedback = user_management_feedback(
        actor=cast(User, current_user),
        event_type='user_management_request_rejected',
        status=status,
        title=title,
        message=message,
        target=target,
    )
    return finish(feedback)


@bp.get('/')
@permission_required('users.view')
def index():
    filters = normalize_user_filters(request.args.to_dict())
    payload = build_users_payload(filters, actor=cast(User, current_user))
    template = 'users/partials/_content.html' if request.headers.get('HX-Request') else 'users/index.html'
    return render_template(template, **payload)


@bp.route('/new', methods=['GET', 'POST'])
@permission_required('users.manage')
def create():
    actor = cast(User, current_user)
    form = UserForm()
    assign_user_form_choices(form, actor=actor)
    form.is_active.data = True if request.method == 'GET' else form.is_active.data

    if form.validate_on_submit():
        if form.auth_source.data != 'database':
            form.auth_source.errors = [
                *form.auth_source.errors,
                'External identities must be selected through LDAP Directory Provisioning.',
            ]
            return render_template(
                'users/form.html',
                form=form,
                mode='create',
                user=None,
                can_manage_admin_fields=actor.is_super_admin,
                super_admin_eligible=True,
            )
        allowed, message = can_create_user(
            actor,
            requested_role_id=form.role_id.data,
            requested_is_super_admin=bool(form.is_super_admin.data),
        )
        if not allowed:
            return reject('User creation blocked', message or 'This account cannot be created.')

        user = create_or_update_user(form)
        if user.auth_source == 'database' and not form.password.data:
            form.password.errors = [*form.password.errors, 'Password is required for Local Database users.']
        else:
            try:
                db.session.flush()
                record_admin_event(
                    actor=actor,
                    action='user.created',
                    target=user,
                    summary=f'Created user {user.username}.',
                    metadata={'auth_source': user.auth_source, 'role': user.role_name},
                )
                db.session.commit()
                feedback = user_management_feedback(
                    actor=actor,
                    event_type='user_created',
                    status='success',
                    title='User created',
                    message=f'{user.username} is ready for administrative use.',
                    target=user,
                )
                return finish(feedback)
            except IntegrityError:
                db.session.rollback()
                form.username.errors = [*form.username.errors, 'Username or email already exists.']

    return render_template(
        'users/form.html',
        form=form,
        mode='create',
        user=None,
        can_manage_admin_fields=actor.is_super_admin,
        super_admin_eligible=True,
    )


@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@permission_required('users.manage')
def edit(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')

    allowed, message = can_edit_user(
        actor,
        user,
        requested_role_id=user.role_id,
        requested_is_active=user.account_is_active,
        requested_is_super_admin=user.is_super_admin if user.auth_source == 'database' else False,
    )
    if not allowed:
        return reject('User update blocked', message or 'This account cannot be edited.', target=user)

    identity_context = build_user_identity_context(user)
    reset_password_allowed, reset_password_reason = can_reset_user_password(actor, user)

    form = UserForm(obj=user)
    assign_user_form_choices(form, actor=actor)
    if request.method == 'GET':
        form.role_id.data = user.role_id or (user.role_record.id if user.role_record else 0)
        form.is_active.data = user.account_is_active
        form.is_super_admin.data = user.is_super_admin

    if form.validate_on_submit():
        removes_active_super_admin_authority = bool(
            user.is_super_admin
            and user.account_is_active
            and (not bool(form.is_active.data) or not bool(form.is_super_admin.data))
        )
        if removes_active_super_admin_authority:
            lock_active_super_admin_boundary(user)

        allowed, message = can_edit_user(
            actor,
            user,
            requested_role_id=form.role_id.data,
            requested_is_active=bool(form.is_active.data),
            requested_is_super_admin=bool(form.is_super_admin.data),
        )
        if not allowed:
            return reject('User update blocked', message or 'This account cannot be modified.', target=user)
        try:
            create_or_update_user(form, user)
            record_admin_event(
                actor=actor,
                action='user.updated',
                target=user,
                summary=f'Updated user {user.username}.',
                metadata={'auth_source': user.auth_source, 'role': user.role_name},
            )
            db.session.commit()
            feedback = user_management_feedback(
                actor=actor,
                event_type='user_updated',
                status='success',
                title='User updated',
                message=f'{user.username} administrative profile was updated.',
                target=user,
            )
            return finish(feedback)
        except IntegrityError:
            db.session.rollback()
            form.username.errors = [*form.username.errors, 'Username or email already exists.']

    return render_template(
        'users/form.html',
        form=form,
        mode='edit',
        user=user,
        can_manage_admin_fields=actor.is_super_admin,
        super_admin_eligible=user.auth_source == 'database',
        identity_context=identity_context,
        reset_password_allowed=reset_password_allowed,
        reset_password_reason=reset_password_reason,
        is_self_edit=actor.id == user.id,
    )


@bp.post('/<int:user_id>/activate')
@permission_required('users.activate')
def activate(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    allowed, message = can_activate_user(actor, user)
    if not allowed:
        return reject('Activation blocked', message or 'This account cannot be activated.', target=user)
    set_user_active(user, True)
    record_admin_event(actor=actor, action='user.activated', target=user, summary=f'Activated user {user.username}.')
    db.session.commit()
    return finish(
        user_management_feedback(
            actor=actor,
            event_type='user_activated',
            status='success',
            title='User activated',
            message=f'{user.username} can authenticate again.',
            target=user,
        )
    )


@bp.post('/<int:user_id>/deactivate')
@permission_required('users.activate')
def deactivate(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    lock_active_super_admin_boundary(user)
    allowed, message = can_deactivate_user(actor, user)
    if not allowed:
        return reject('Deactivation blocked', message or 'This account cannot be deactivated.', target=user)
    set_user_active(user, False)
    record_admin_event(
        actor=actor, action='user.deactivated', target=user, summary=f'Deactivated user {user.username}.'
    )
    db.session.commit()
    return finish(
        user_management_feedback(
            actor=actor,
            event_type='user_deactivated',
            status='warning',
            title='User deactivated',
            message=f'{user.username} can no longer authenticate.',
            target=user,
        )
    )


@bp.route('/<int:user_id>/reset-password', methods=['GET', 'POST'])
@permission_required('users.reset_password')
def reset_password(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    allowed, message = can_reset_user_password(actor, user)
    if not allowed:
        return reject(
            'Password reset blocked', message or 'Password reset is not allowed for this account.', target=user
        )
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data or '')
        record_admin_event(
            actor=actor, action='user.password_reset', target=user, summary=f'Reset password for user {user.username}.'
        )
        db.session.commit()
        return finish(
            user_management_feedback(
                actor=actor,
                event_type='user_password_reset',
                status='success',
                title='Password reset completed',
                message=f'A new Local Database password was set for {user.username}; existing sessions were revoked.',
                target=user,
            )
        )
    return render_template('users/reset_password.html', form=form, user=user)


@bp.post('/<int:user_id>/restore')
@permission_required('users.activate')
def restore(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    allowed, message = can_restore_user(actor, user)
    if not allowed:
        return reject('Restore blocked', message or 'This account cannot be restored.', target=user)
    restore_user(user)
    record_admin_event(actor=actor, action='user.restored', target=user, summary=f'Restored user {user.username}.')
    db.session.commit()
    return finish(
        user_management_feedback(
            actor=actor,
            event_type='user_restored',
            status='success',
            title='User restored',
            message=f'{user.username} returned to inactive administration and must be activated explicitly.',
            target=user,
        )
    )


@bp.post('/<int:user_id>/delete')
@permission_required('users.delete')
def delete(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    lock_active_super_admin_boundary(user)
    allowed, message = can_delete_user(actor, user)
    if not allowed:
        return reject('Deletion blocked', message or 'This account cannot be deleted.', target=user)
    soft_delete_user(user)
    record_admin_event(actor=actor, action='user.deleted', target=user, summary=f'Soft deleted user {user.username}.')
    db.session.commit()
    return finish(
        user_management_feedback(
            actor=actor,
            event_type='user_deleted',
            status='warning',
            title='User soft deleted',
            message=f'{user.username} was removed from active administration.',
            target=user,
        )
    )
