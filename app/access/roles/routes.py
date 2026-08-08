from __future__ import annotations

from typing import cast

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.roles.forms import DeleteRoleForm, RoleForm
from app.access.roles.presentation import (
    build_role_form_context,
    build_roles_index_context,
    normalize_role_filters,
)
from app.access.roles.service import (
    RoleInputError,
    create_custom_role,
    lock_role_for_mutation,
    role_version_matches,
    role_version_token,
)
from app.extensions.db import db
from app.models import Role, User
from app.rbac.decorators import permission_required
from app.rbac.notifications import role_access_feedback
from app.rbac.service import (
    expand_permission_ids,
    get_role_delete_blockers,
    normalize_role_slug,
    replace_role_permissions,
    role_slug_exists,
    seed_default_rbac,
)
from app.users.service import record_admin_event

bp = Blueprint('roles', __name__)


@bp.get('/')
@permission_required('roles.view')
def index():
    # Kept intentionally for now because the RBAC registry still uses convergent
    # seeding across Access surfaces. The ownership of that convergence will be
    # decided together with Permission Catalog before the Access final lock.
    seed_default_rbac()
    actor = cast(User, current_user._get_current_object())
    filters = normalize_role_filters(request.args.to_dict())
    payload = build_roles_index_context(
        can_manage_roles=actor.has_permission('roles.manage'),
        filters=filters,
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('access/roles/partials/_registry.html', **payload)
    return render_template('access/roles/index.html', **payload)


@bp.route('/new', methods=['GET', 'POST'])
@permission_required('roles.manage')
def create():
    seed_default_rbac()
    form = RoleForm()
    if request.method == 'GET':
        form.is_active.data = True

    selected_permission_ids = {int(value) for value in request.form.getlist('permission_ids') if value.isdigit()}
    if form.validate_on_submit():
        try:
            role = create_custom_role(
                actor=cast(User, current_user),
                name=form.name.data,
                display_name=form.display_name.data,
                description=form.description.data,
                is_active=bool(form.is_active.data),
                selected_permission_ids=selected_permission_ids,
            )
        except RoleInputError as exc:
            form.name.errors = [*form.name.errors, str(exc)]
        else:
            role_access_feedback(
                actor=cast(User, current_user),
                event_type='rbac_role_created',
                status='success',
                title='Custom role created',
                message=f'{role.display_name} is ready for user assignment.',
                role=role,
            )
            return redirect(url_for('access.roles.index'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return render_template(
        'access/roles/form.html',
        **build_role_form_context(
            form=form,
            role=None,
            clone_source=None,
            view_only=False,
            selected_permission_ids=selected_permission_ids,
        ),
    )


@bp.route('/<int:role_id>/clone', methods=['GET', 'POST'])
@permission_required('roles.manage')
def clone(role_id: int):
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
        return redirect(url_for('access.roles.index'))

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
        try:
            role = create_custom_role(
                actor=cast(User, current_user),
                name=form.name.data,
                display_name=form.display_name.data,
                description=form.description.data,
                is_active=bool(form.is_active.data),
                selected_permission_ids=selected_permission_ids,
                clone_source=source_role,
            )
        except RoleInputError as exc:
            form.name.errors = [*form.name.errors, str(exc)]
        else:
            role_access_feedback(
                actor=cast(User, current_user),
                event_type='rbac_role_cloned',
                status='success',
                title='Default role cloned',
                message=f'{source_role.display_name} was cloned as {role.display_name}.',
                role=role,
                detail='The cloned role is custom and can now be adjusted independently.',
            )
            return redirect(url_for('access.roles.index'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return render_template(
        'access/roles/form.html',
        **build_role_form_context(
            form=form,
            role=None,
            clone_source=source_role,
            view_only=False,
            selected_permission_ids=selected_permission_ids,
        ),
    )


@bp.get('/<int:role_id>')
@permission_required('roles.view')
def detail(role_id: int):
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
        return redirect(url_for('access.roles.index'))

    form = RoleForm(obj=role)
    form.is_active.data = role.is_active
    form.role_version.data = role_version_token(role)
    return render_template(
        'access/roles/form.html',
        **build_role_form_context(
            form=form,
            role=role,
            clone_source=None,
            view_only=True,
            selected_permission_ids={permission.id for permission in role.permissions},
        ),
    )


@bp.route('/<int:role_id>/edit', methods=['GET', 'POST'])
@permission_required('roles.manage')
def edit(role_id: int):
    role = db.session.get(Role, role_id)
    if role is None:
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_update_rejected',
            status='error',
            title='Role update unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('access.roles.index'))
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
        return redirect(url_for('access.roles.detail', role_id=role.id))

    form = RoleForm(obj=role)
    selected_permission_ids = {permission.id for permission in role.permissions}
    if request.method == 'GET':
        form.is_active.data = role.is_active
        form.role_version.data = role_version_token(role)
    else:
        selected_permission_ids = {int(value) for value in request.form.getlist('permission_ids') if value.isdigit()}

    if form.validate_on_submit():
        locked_role = lock_role_for_mutation(role_id)
        if locked_role is None:
            db.session.rollback()
            return redirect(url_for('access.roles.index'))
        role = locked_role

        if not role_version_matches(role, form.role_version.data):
            current_version = role_version_token(role)
            db.session.rollback()
            role = db.session.get(Role, role_id)
            form.role_version.data = current_version
            form.role_version.errors = [
                *form.role_version.errors,
                'This role changed after the page was opened. Review the latest role state before saving again.',
            ]
        else:
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
                    return redirect(url_for('access.roles.index'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return render_template(
        'access/roles/form.html',
        **build_role_form_context(
            form=form,
            role=role,
            clone_source=None,
            view_only=False,
            selected_permission_ids=selected_permission_ids,
        ),
    )


@bp.post('/<int:role_id>/delete')
@permission_required('roles.manage')
def delete(role_id: int):
    role = lock_role_for_mutation(role_id)
    if role is None:
        db.session.rollback()
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_rejected',
            status='error',
            title='Role deletion unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('access.roles.index'))

    form = DeleteRoleForm()
    if not form.validate_on_submit() or str(form.role_id.data) != str(role.id):
        db.session.rollback()
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_rejected',
            status='error',
            title='Role deletion rejected',
            message='The role deletion request could not be validated.',
            role=role,
        )
        return redirect(url_for('access.roles.index'))
    if role.is_system:
        db.session.rollback()
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_rejected',
            status='warning',
            title='Default role is protected',
            message='Default roles cannot be deleted.',
            role=role,
        )
        return redirect(url_for('access.roles.index'))
    if not role_version_matches(role, form.role_version.data):
        db.session.rollback()
        role_access_feedback(
            actor=cast(User, current_user),
            event_type='rbac_role_delete_blocked',
            status='warning',
            title='Role deletion requires review',
            message='The role changed after the registry was loaded.',
            role=role,
            detail='Refresh Roles & Access and review the latest role state before deleting it.',
        )
        return redirect(url_for('access.roles.index'))

    blockers = get_role_delete_blockers(role)
    if blockers['assigned_users'] or blockers['identity_providers']:
        db.session.rollback()
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
        return redirect(url_for('access.roles.index'))

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
    return redirect(url_for('access.roles.index'))
