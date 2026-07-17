from __future__ import annotations

from typing import Any, cast

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import IdentityProvider, User
from app.rbac.decorators import permission_required
from app.rbac.service import seed_default_rbac
from app.users.forms import (ExternalIdentityProvisionForm, ExternalIdentitySearchForm, IdentityProviderForm, ResetPasswordForm, UserForm)
from app.users.notifications import user_management_feedback
from app.users.external import assign_projection_role_choices, assign_provider_choices, provision_external_identity, IdentityProjectionError
from app.users.providers import ExternalProviderError, ExternalIdentity, LdapDirectoryProvider
from app.users.service import (
    assign_user_form_choices,
    build_users_payload,
    can_activate_user,
    can_create_user,
    can_deactivate_user,
    can_delete_user,
    can_edit_user,
    can_reset_user_password,
    can_restore_user,
    create_or_update_user,
    normalize_user_filters,
    record_admin_event,
    set_user_active,
    soft_delete_user,
    restore_user,
)


bp = Blueprint('users', __name__, url_prefix='/users')

def render_users_content(feedback: dict[str, Any] | None = None) -> str:
    filters = normalize_user_filters(request.values.to_dict())
    payload = build_users_payload(filters, actor=cast(User, current_user))
    content = render_template('users/partials/_content.html', **payload)
    if feedback is None:
        return content
    toast = render_template(
        'components/navigation/_quick_sync_result.html',
        **feedback,
        toast_oob=True,
    )
    return f'{content}{toast}'

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
    seed_default_rbac()
    actor = cast(User, current_user)
    form = UserForm()
    assign_user_form_choices(form, include_admin_roles=actor.is_super_admin)
    form.is_active.data = True if request.method == 'GET' else form.is_active.data

    if form.validate_on_submit():
        if form.auth_source.data != 'database':
            form.auth_source.errors = [*form.auth_source.errors, 'External identities must be selected through LDAP Directory Provisioning.']
            return render_template('users/form.html', form=form, mode='create', user=None, can_manage_admin_fields=actor.is_super_admin)
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

    return render_template('users/form.html', form=form, mode='create', user=None, can_manage_admin_fields=actor.is_super_admin)

@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@permission_required('users.manage')
def edit(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')

    allowed, message = can_edit_user(actor, user, requested_role_id=user.role_id, requested_is_active=user.account_is_active, requested_is_super_admin=user.is_super_admin)
    if not allowed:
        return reject('User update blocked', message or 'This account cannot be edited.', target=user)

    form = UserForm(obj=user)
    assign_user_form_choices(form, include_admin_roles=actor.is_super_admin)
    if request.method == 'GET':
        form.role_id.data = user.role_id or (user.role_record.id if user.role_record else 0)
        form.is_active.data = user.account_is_active
        form.is_super_admin.data = user.is_super_admin

    if form.validate_on_submit():
        allowed, message = can_edit_user(actor, user, requested_role_id=form.role_id.data, requested_is_active=bool(form.is_active.data), requested_is_super_admin=bool(form.is_super_admin.data))
        if not allowed:
            return reject('User update blocked', message or 'This account cannot be modified.', target=user)
        try:
            create_or_update_user(form, user)
            record_admin_event(actor=actor, action='user.updated', target=user, summary=f'Updated user {user.username}.', metadata={'auth_source': user.auth_source, 'role': user.role_name})
            db.session.commit()
            feedback = user_management_feedback(actor=actor, event_type='user_updated', status='success', title='User updated', message=f'{user.username} administrative profile was updated.', target=user)
            return finish(feedback)
        except IntegrityError:
            db.session.rollback()
            form.username.errors = [*form.username.errors, 'Username or email already exists.']

    return render_template('users/form.html', form=form, mode='edit', user=user, can_manage_admin_fields=actor.is_super_admin)

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
    return finish(user_management_feedback(actor=actor, event_type='user_activated', status='success', title='User activated', message=f'{user.username} can authenticate again.', target=user))

@bp.post('/<int:user_id>/deactivate')
@permission_required('users.activate')
def deactivate(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    allowed, message = can_deactivate_user(actor, user)
    if not allowed:
        return reject('Deactivation blocked', message or 'This account cannot be deactivated.', target=user)
    set_user_active(user, False)
    record_admin_event(actor=actor, action='user.deactivated', target=user, summary=f'Deactivated user {user.username}.')
    db.session.commit()
    return finish(user_management_feedback(actor=actor, event_type='user_deactivated', status='warning', title='User deactivated', message=f'{user.username} can no longer authenticate.', target=user))

@bp.route('/<int:user_id>/reset-password', methods=['GET', 'POST'])
@permission_required('users.reset_password')
def reset_password(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    allowed, message = can_reset_user_password(actor, user)
    if not allowed:
        return reject('Password reset blocked', message or 'Password reset is not allowed for this account.', target=user)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data or '')
        record_admin_event(actor=actor, action='user.password_reset', target=user, summary=f'Reset password for user {user.username}.')
        db.session.commit()
        return finish(user_management_feedback(actor=actor, event_type='user_password_reset', status='success', title='Password reset completed', message=f'A new Local Database password was set for {user.username}.', target=user))
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
    return finish(user_management_feedback(actor=actor, event_type='user_restored', status='success', title='User restored', message=f'{user.username} returned to inactive administration and must be activated explicitly.', target=user))

@bp.post('/<int:user_id>/delete')
@permission_required('users.delete')
def delete(user_id: int):
    actor = cast(User, current_user)
    user = db.session.get(User, user_id)
    if user is None:
        return reject('User unavailable', 'The requested user record was not found.', status='error')
    allowed, message = can_delete_user(actor, user)
    if not allowed:
        return reject('Deletion blocked', message or 'This account cannot be deleted.', target=user)
    soft_delete_user(user)
    record_admin_event(actor=actor, action='user.deleted', target=user, summary=f'Soft deleted user {user.username}.')
    db.session.commit()
    return finish(user_management_feedback(actor=actor, event_type='user_deleted', status='warning', title='User soft deleted', message=f'{user.username} was removed from active administration.', target=user))

@bp.route('/providers', methods=['GET'])
@permission_required('users.manage')
def providers():
    items = IdentityProvider.query.order_by(IdentityProvider.provider_type.asc(), IdentityProvider.display_name.asc()).all()
    return render_template('users/providers/index.html', providers=items)


@bp.route('/providers/new', methods=['GET', 'POST'])
@permission_required('users.manage')
def create_provider():
    form = IdentityProviderForm()
    if form.validate_on_submit():
        provider = IdentityProvider()
        _apply_provider_form(provider, form)
        db.session.add(provider)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.key.errors = [*form.key.errors, 'Provider key already exists.']
        else:
            user_management_feedback(
                actor=cast(User, current_user), event_type='identity_provider_created', status='success',
                title='Identity provider created', message=f'{provider.display_name} configuration was created.',
            )
            return redirect(url_for('users.providers'))
    return render_template('users/providers/form.html', form=form, provider=None)


@bp.route('/providers/<int:provider_id>/edit', methods=['GET', 'POST'])
@permission_required('users.manage')
def edit_provider(provider_id: int):
    provider = db.get_or_404(IdentityProvider, provider_id)
    form = IdentityProviderForm(obj=provider)
    if form.validate_on_submit():
        _apply_provider_form(provider, form)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.key.errors = [*form.key.errors, 'Provider key already exists.']
        else:
            user_management_feedback(
                actor=cast(User, current_user), event_type='identity_provider_updated', status='success',
                title='Identity provider updated', message=f'{provider.display_name} configuration was updated.',
            )
            return redirect(url_for('users.providers'))
    return render_template('users/providers/form.html', form=form, provider=provider)


@bp.post('/providers/<int:provider_id>/validate')
@permission_required('users.manage')
def validate_provider(provider_id: int):
    provider = db.get_or_404(IdentityProvider, provider_id)
    status, title, message = 'success', 'Provider validation passed', f'{provider.display_name} accepted an LDAP service connection.'
    try:
        if provider.provider_type != 'ldap':
            raise ExternalProviderError('OIDC validation will be enabled with the OIDC implementation phase.')
        LdapDirectoryProvider(provider).validate()
    except ExternalProviderError as exc:
        status, title, message = 'error', 'Provider validation failed', str(exc)
    user_management_feedback(
        actor=cast(User, current_user), event_type='identity_provider_validated', status=status,
        title=title, message=message,
    )
    return redirect(url_for('users.providers'))


def _apply_provider_form(provider: IdentityProvider, form: IdentityProviderForm) -> None:
    provider.key = (form.key.data or '').strip().lower()
    provider.display_name = (form.display_name.data or '').strip()
    provider.provider_type = form.provider_type.data
    provider.enabled = bool(form.enabled.data)
    provider.jit_enabled = bool(form.jit_enabled.data)
    provider.server_uri = (form.server_uri.data or '').strip() or None
    provider.base_dn = (form.base_dn.data or '').strip() or None
    provider.bind_dn = (form.bind_dn.data or '').strip() or None
    provider.bind_password_env = (form.bind_password_env.data or '').strip() or None
    provider.user_filter = (form.user_filter.data or '').strip() or None
    provider.tls_mode = form.tls_mode.data
    provider.username_attribute = (form.username_attribute.data or '').strip()
    provider.email_attribute = (form.email_attribute.data or '').strip()
    provider.display_name_attribute = (form.display_name_attribute.data or '').strip()
    provider.stable_id_attribute = (form.stable_id_attribute.data or '').strip()
    provider.oidc_issuer = (form.oidc_issuer.data or '').strip() or None
    provider.oidc_client_id = (form.oidc_client_id.data or '').strip() or None
    provider.oidc_client_secret_env = (form.oidc_client_secret_env.data or '').strip() or None


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
                results = LdapDirectoryProvider(selected_provider).search(search_form.query.data or '')
            except ExternalProviderError as exc:
                user_management_feedback(
                    actor=cast(User, current_user), event_type='external_identity_search_failed', status='error',
                    title='Directory search failed', message=str(exc),
                )
    return render_template(
        'users/external_identities.html', search_form=search_form, provision_form=provision_form,
        results=results, selected_provider=selected_provider,
    )


@bp.post('/external-identities/provision')
@permission_required('users.manage')
def provision_identity():
    form = ExternalIdentityProvisionForm()
    assign_projection_role_choices(form, include_admin_roles=cast(User, current_user).is_super_admin)
    if not form.validate_on_submit():
        user_management_feedback(
            actor=cast(User, current_user), event_type='external_identity_provision_failed', status='error',
            title='Provisioning failed', message='The external identity request was incomplete.',
        )
        return redirect(url_for('users.external_identities'))
    provider = db.session.get(IdentityProvider, int(form.provider_id.data))
    if provider is None or not provider.enabled or provider.provider_type != 'ldap':
        user_management_feedback(
            actor=cast(User, current_user), event_type='external_identity_provision_failed', status='error',
            title='Provisioning failed', message='The selected LDAP provider is unavailable.',
        )
        return redirect(url_for('users.external_identities'))
    identity = ExternalIdentity(
        subject=form.subject.data, username=form.external_username.data,
        email=form.email.data or None, display_name=form.display_name.data or None,
        distinguished_name=form.distinguished_name.data,
    )
    try:
        user = provision_external_identity(
            provider=provider, identity=identity, role_id=form.role_id.data,
            is_active=bool(form.is_active.data),
        )
        record_admin_event(
            actor=cast(User, current_user), action='user.external_identity_provisioned', target=user,
            summary=f'Provisioned LDAP identity {user.username}.', metadata={'provider_key': provider.key},
        )
        db.session.commit()
    except IdentityProjectionError as exc:
        db.session.rollback()
        user_management_feedback(
            actor=cast(User, current_user), event_type='external_identity_provision_failed', status='error',
            title='Provisioning failed', message=str(exc),
        )
    else:
        user_management_feedback(
            actor=cast(User, current_user), event_type='external_identity_provisioned', status='success',
            title='LDAP user provisioned', message=f'{user.username} can authenticate through {provider.display_name}.', target=user,
        )
    return redirect(url_for('users.index'))
