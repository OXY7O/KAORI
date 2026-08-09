from __future__ import annotations

from typing import Any, cast

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.auth.provider_configuration import apply_identity_provider_configuration, validate_identity_provider
from app.auth.providers.browser import SsoProviderError
from app.auth.providers.ldap import ExternalIdentity, ExternalProviderError, LdapDirectoryClient
from app.auth.sso import SsoAdmissionError
from app.extensions.db import db
from app.models import IdentityProvider, Role, User
from app.rbac.decorators import permission_required
from app.users.external import (
    IdentityProjectionError,
    assign_projection_role_choices,
    assign_provider_choices,
    provision_external_identity,
)
from app.users.forms import (
    ExternalIdentityProvisionForm,
    ExternalIdentitySearchForm,
    IdentityProviderForm,
    ResetPasswordForm,
    UserForm,
)
from app.users.notifications import user_management_feedback
from app.users.provider_forms import identity_provider_configuration_from_form
from app.users.service import (
    assign_user_form_choices,
    build_identity_provider_payload,
    build_user_identity_context,
    build_users_payload,
    can_activate_user,
    can_create_user,
    can_deactivate_user,
    can_delete_user,
    can_edit_user,
    can_reset_user_password,
    can_restore_user,
    create_or_update_user,
    normalize_provider_filters,
    normalize_user_filters,
    lock_active_super_admin_boundary,
    record_admin_event,
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
    assign_user_form_choices(form, include_admin_roles=actor.is_super_admin)
    form.is_active.data = True if request.method == 'GET' else form.is_active.data

    if form.validate_on_submit():
        if form.auth_source.data != 'database':
            form.auth_source.errors = [
                *form.auth_source.errors,
                'External identities must be selected through LDAP Directory Provisioning.',
            ]
            return render_template(
                'users/form.html', form=form, mode='create', user=None, can_manage_admin_fields=actor.is_super_admin
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
        'users/form.html', form=form, mode='create', user=None, can_manage_admin_fields=actor.is_super_admin
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
        requested_is_super_admin=user.is_super_admin,
    )
    if not allowed:
        return reject('User update blocked', message or 'This account cannot be edited.', target=user)

    identity_context = build_user_identity_context(user)
    reset_password_allowed, reset_password_reason = can_reset_user_password(actor, user)

    form = UserForm(obj=user)
    assign_user_form_choices(form, include_admin_roles=actor.is_super_admin)
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
                message=f'A new Local Database password was set for {user.username}.',
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


@bp.route('/providers', methods=['GET'])
@permission_required('users.manage')
def providers():
    filters = normalize_provider_filters(request.args.to_dict())
    payload = build_identity_provider_payload(filters)
    if request.headers.get('HX-Request') == 'true':
        return render_template('users/providers/partials/_registry.html', **payload)
    return render_template('users/providers/index.html', **payload)


@bp.route('/providers/new', methods=['GET', 'POST'])
@permission_required('users.manage')
def create_provider():
    form = IdentityProviderForm()
    _assign_provider_role_choices(form)
    if form.validate_on_submit():
        provider = IdentityProvider()
        apply_identity_provider_configuration(provider, identity_provider_configuration_from_form(form))
        db.session.add(provider)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.key.errors = [*form.key.errors, 'Provider key already exists.']
        else:
            user_management_feedback(
                actor=cast(User, current_user),
                event_type='identity_provider_created',
                status='success',
                title='Identity provider created',
                message=f'{provider.display_name} configuration was created.',
            )
            return redirect(url_for('users.providers'))
    return render_template('users/providers/form.html', form=form, provider=None)


@bp.route('/providers/<int:provider_id>/edit', methods=['GET', 'POST'])
@permission_required('users.manage')
def edit_provider(provider_id: int):
    provider = db.get_or_404(IdentityProvider, provider_id)
    form = IdentityProviderForm(obj=provider)
    _assign_provider_role_choices(form)
    if form.validate_on_submit():
        apply_identity_provider_configuration(provider, identity_provider_configuration_from_form(form))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.key.errors = [*form.key.errors, 'Provider key already exists.']
        else:
            user_management_feedback(
                actor=cast(User, current_user),
                event_type='identity_provider_updated',
                status='success',
                title='Identity provider updated',
                message=f'{provider.display_name} configuration was updated.',
            )
            return redirect(url_for('users.providers'))
    return render_template('users/providers/form.html', form=form, provider=provider)


@bp.post('/providers/test')
@bp.post('/providers/<int:provider_id>/test')
@permission_required('users.manage')
def test_provider_configuration(provider_id: int | None = None):
    provider = db.get_or_404(IdentityProvider, provider_id) if provider_id is not None else None
    form = IdentityProviderForm()
    _assign_provider_role_choices(form)
    test_result: dict[str, str]

    if form.validate_on_submit():
        candidate = IdentityProvider()
        apply_identity_provider_configuration(candidate, identity_provider_configuration_from_form(form))
        try:
            message = validate_identity_provider(candidate)
        except (ExternalProviderError, SsoProviderError, SsoAdmissionError) as exc:
            test_result = {
                'status': 'error',
                'title': 'Connection Test Failed',
                'message': str(exc),
            }
        else:
            test_result = {
                'status': 'success',
                'title': 'Connection Test Passed',
                'message': message,
            }
    else:
        test_result = {
            'status': 'error',
            'title': 'Connection Test Blocked',
            'message': 'Complete the required provider fields before testing the current configuration.',
        }

    return render_template(
        'users/providers/form.html',
        form=form,
        provider=provider,
        test_result=test_result,
    )


@bp.post('/providers/<int:provider_id>/validate')
@permission_required('users.manage')
def validate_provider(provider_id: int):
    provider = db.get_or_404(IdentityProvider, provider_id)
    status, title = 'success', 'Provider validation passed'
    try:
        message = validate_identity_provider(provider)
    except (ExternalProviderError, SsoProviderError, SsoAdmissionError) as exc:
        status, title, message = 'error', 'Provider validation failed', str(exc)
    user_management_feedback(
        actor=cast(User, current_user),
        event_type='identity_provider_validated',
        status=status,
        title=title,
        message=message,
    )
    return redirect(url_for('users.providers'))


def _assign_provider_role_choices(form: IdentityProviderForm) -> None:
    roles = Role.query.filter_by(is_active=True).filter(Role.name != 'admin').order_by(Role.display_name.asc()).all()
    role_choices: list[tuple[Any, str] | tuple[Any, str, dict[str, Any]]] = [
        (0, 'Select role'),
        *((role.id, role.display_name) for role in roles),
    ]
    form.default_role_id.choices = role_choices


@bp.route('/external-identities', methods=['GET', 'POST'])
@permission_required('users.manage')
def external_identities():
    search_form = ExternalIdentitySearchForm()
    provision_form = ExternalIdentityProvisionForm()
    assign_provider_choices(search_form)
    assign_projection_role_choices(provision_form, include_admin_roles=cast(User, current_user).is_super_admin)
    results: list[ExternalIdentity] = []
    selected_provider = None
    if search_form.validate_on_submit() and search_form.submit.data:
        selected_provider = db.session.get(IdentityProvider, search_form.provider_id.data)
        if selected_provider is not None:
            try:
                results = LdapDirectoryClient(selected_provider).search(search_form.query.data or '')
            except ExternalProviderError as exc:
                user_management_feedback(
                    actor=cast(User, current_user),
                    event_type='external_identity_search_failed',
                    status='error',
                    title='Directory search failed',
                    message=str(exc),
                )
    return render_template(
        'users/external_identities.html',
        search_form=search_form,
        provision_form=provision_form,
        results=results,
        selected_provider=selected_provider,
    )


@bp.post('/external-identities/provision')
@permission_required('users.manage')
def provision_identity():
    form = ExternalIdentityProvisionForm()
    assign_projection_role_choices(form, include_admin_roles=cast(User, current_user).is_super_admin)
    if not form.validate_on_submit():
        user_management_feedback(
            actor=cast(User, current_user),
            event_type='external_identity_provision_failed',
            status='error',
            title='Provisioning failed',
            message='The external identity request was incomplete.',
        )
        return redirect(url_for('users.external_identities'))
    provider_id_raw = (form.provider_id.data or '').strip()
    role_id = form.role_id.data
    subject = (form.subject.data or '').strip()
    external_username = (form.external_username.data or '').strip()
    distinguished_name = (form.distinguished_name.data or '').strip()
    if (
        not provider_id_raw.isdigit()
        or role_id is None
        or not subject
        or not external_username
        or not distinguished_name
    ):
        user_management_feedback(
            actor=cast(User, current_user),
            event_type='external_identity_provision_failed',
            status='error',
            title='Provisioning failed',
            message='The external identity request was incomplete.',
        )
        return redirect(url_for('users.external_identities'))

    provider = db.session.get(IdentityProvider, int(provider_id_raw))
    if provider is None or not provider.enabled or provider.provider_type != 'ldap':
        user_management_feedback(
            actor=cast(User, current_user),
            event_type='external_identity_provision_failed',
            status='error',
            title='Provisioning failed',
            message='The selected LDAP provider is unavailable.',
        )
        return redirect(url_for('users.external_identities'))
    identity = ExternalIdentity(
        subject=subject,
        username=external_username,
        email=(form.email.data or '').strip() or None,
        display_name=(form.display_name.data or '').strip() or None,
        distinguished_name=distinguished_name,
    )
    try:
        user = provision_external_identity(
            provider=provider,
            identity=identity,
            role_id=role_id,
            is_active=bool(form.is_active.data),
        )
        record_admin_event(
            actor=cast(User, current_user),
            action='user.external_identity_provisioned',
            target=user,
            summary=f'Provisioned LDAP identity {user.username}.',
            metadata={'provider_key': provider.key},
        )
        db.session.commit()
    except IdentityProjectionError as exc:
        db.session.rollback()
        user_management_feedback(
            actor=cast(User, current_user),
            event_type='external_identity_provision_failed',
            status='error',
            title='Provisioning failed',
            message=str(exc),
        )
    else:
        user_management_feedback(
            actor=cast(User, current_user),
            event_type='external_identity_provisioned',
            status='success',
            title='LDAP user provisioned',
            message=f'{user.username} can authenticate through {provider.display_name}.',
            target=user,
        )
    return redirect(url_for('users.index'))
