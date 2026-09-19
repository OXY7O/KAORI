from __future__ import annotations

from typing import cast

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.access.rbac.notifications import role_access_feedback
from app.access.rbac.policy import role_is_mutation_protected, role_is_protected_default
from app.access.rbac.service import expand_permission_ids, get_role_delete_blockers
from app.access.roles.forms import DeleteRoleForm, RoleForm
from app.access.roles.presentation import (
    build_role_detail_context,
    build_role_form_context,
    build_roles_index_context,
    normalize_role_filters,
)
from app.access.roles.service import (
    RoleDelegationError,
    RoleImpactAcknowledgementRequired,
    RoleInputError,
    create_custom_role,
    delete_custom_role,
    ensure_role_within_delegation_boundary,
    get_role,
    lock_role_for_mutation,
    role_version_matches,
    role_version_token,
    rollback_role_transaction,
    update_custom_role,
)
from app.models import Role, User

bp = Blueprint('roles', __name__)


def _permission_error(form: RoleForm, message: str) -> None:
    form.permission_scope.errors = [*form.permission_scope.errors, message]


def _render_role_form(
    *,
    form: RoleForm,
    actor: User,
    role: Role | None,
    clone_source: Role | None,
    view_only: bool,
    selected_permission_ids: set[int],
):
    return render_template(
        'access/roles/form.html',
        **build_role_form_context(
            form=form,
            actor=actor,
            role=role,
            clone_source=clone_source,
            view_only=view_only,
            selected_permission_ids=selected_permission_ids,
        ),
    )


@bp.get('/')
@permission_required('roles.view')
def index():
    actor = cast(User, current_user._get_current_object())
    filters = normalize_role_filters(request.args.to_dict())
    payload = build_roles_index_context(can_manage_roles=actor.has_permission('roles.manage'), filters=filters)
    if request.headers.get('HX-Request') == 'true':
        return render_template('access/roles/partials/_registry.html', **payload)
    return render_template('access/roles/index.html', **payload)


@bp.route('/new', methods=['GET', 'POST'])
@permission_required('roles.manage')
def create():
    actor = cast(User, current_user._get_current_object())
    form = RoleForm()
    if request.method == 'GET':
        form.is_active.data = True

    selected_permission_ids = {int(value) for value in request.form.getlist('permission_ids') if value.isdigit()}
    if form.validate_on_submit():
        try:
            role = create_custom_role(
                actor=actor,
                name=form.name.data,
                display_name=form.display_name.data,
                description=form.description.data,
                is_active=bool(form.is_active.data),
                selected_permission_ids=selected_permission_ids,
            )
        except RoleDelegationError as exc:
            _permission_error(form, str(exc))
        except RoleInputError as exc:
            form.name.errors = [*form.name.errors, str(exc)]
        else:
            role_access_feedback(
                actor=actor,
                event_type='rbac_role_created',
                status='success',
                title='Custom role created',
                message=f'{role.display_name} is ready for user assignment.',
                role=role,
            )
            return redirect(url_for('access.roles.index'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return _render_role_form(
        form=form,
        actor=actor,
        role=None,
        clone_source=None,
        view_only=False,
        selected_permission_ids=selected_permission_ids,
    )


@bp.route('/<int:role_id>/clone', methods=['GET', 'POST'])
@permission_required('roles.manage')
def clone(role_id: int):
    actor = cast(User, current_user._get_current_object())
    source_role = get_role(role_id)
    if source_role is None or not role_is_protected_default(source_role):
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_clone_rejected',
            status='warning',
            title='Role clone blocked',
            message='Only a source-controlled protected default role can be used as a clone source.',
        )
        return redirect(url_for('access.roles.index'))
    try:
        ensure_role_within_delegation_boundary(actor=actor, role=source_role)
    except RoleDelegationError as exc:
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_clone_rejected',
            status='warning',
            title='Role clone exceeds delegation ceiling',
            message=str(exc),
            role=source_role,
        )
        return redirect(url_for('access.roles.detail', role_id=source_role.id))

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
                actor=actor,
                name=form.name.data,
                display_name=form.display_name.data,
                description=form.description.data,
                is_active=bool(form.is_active.data),
                selected_permission_ids=selected_permission_ids,
                clone_source=source_role,
            )
        except RoleDelegationError as exc:
            _permission_error(form, str(exc))
        except RoleInputError as exc:
            form.name.errors = [*form.name.errors, str(exc)]
        else:
            role_access_feedback(
                actor=actor,
                event_type='rbac_role_cloned',
                status='success',
                title='Default role cloned',
                message=f'{source_role.display_name} was cloned as {role.display_name}.',
                role=role,
                detail='The cloned role is custom and can now be adjusted independently.',
            )
            return redirect(url_for('access.roles.index'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return _render_role_form(
        form=form,
        actor=actor,
        role=None,
        clone_source=source_role,
        view_only=False,
        selected_permission_ids=selected_permission_ids,
    )


@bp.get('/<int:role_id>')
@permission_required('roles.view')
def detail(role_id: int):
    actor = cast(User, current_user._get_current_object())
    role = get_role(role_id)
    if role is None:
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_unavailable',
            status='error',
            title='Role unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('access.roles.index'))

    form = RoleForm(obj=role)
    form.is_active.data = role.is_active
    form.role_version.data = role_version_token(role)
    return _render_role_form(
        form=form,
        actor=actor,
        role=role,
        clone_source=None,
        view_only=True,
        selected_permission_ids={permission.id for permission in role.permissions},
    )


@bp.get('/<int:role_id>/details')
@permission_required('roles.view')
def modal_details(role_id: int):
    role = get_role(role_id)
    if role is None:
        return 'Role details unavailable.', 404
    actor = cast(User, current_user._get_current_object())
    return render_template(
        'access/roles/partials/_role_detail.html',
        **build_role_detail_context(role=role, actor=actor),
    )


@bp.route('/<int:role_id>/edit', methods=['GET', 'POST'])
@permission_required('roles.manage')
def edit(role_id: int):
    actor = cast(User, current_user._get_current_object())
    role = get_role(role_id)
    if role is None:
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_update_rejected',
            status='error',
            title='Role update unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('access.roles.index'))
    if role_is_mutation_protected(role):
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_update_rejected',
            status='warning',
            title='Protected role cannot be edited',
            message='Source-controlled or system-owned roles cannot be edited from the Access workspace.',
            role=role,
            detail='Run the explicit RBAC convergence workflow for baseline drift, or clone a canonical default role.',
        )
        return redirect(url_for('access.roles.detail', role_id=role.id))
    try:
        ensure_role_within_delegation_boundary(actor=actor, role=role)
    except RoleDelegationError as exc:
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_update_rejected',
            status='warning',
            title='Role update exceeds delegation ceiling',
            message=str(exc),
            role=role,
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
            rollback_role_transaction()
            return redirect(url_for('access.roles.index'))
        role = locked_role

        if not role_version_matches(role, form.role_version.data):
            current_version = role_version_token(role)
            rollback_role_transaction()
            role = get_role(role_id)
            form.role_version.data = current_version
            form.role_version.errors = [
                *form.role_version.errors,
                'This role changed after the page was opened. Review the latest role state before saving again.',
            ]
        else:
            try:
                effective_permission_ids = update_custom_role(
                    actor=actor,
                    role=role,
                    name=form.name.data,
                    display_name=form.display_name.data,
                    description=form.description.data,
                    is_active=bool(form.is_active.data),
                    selected_permission_ids=selected_permission_ids,
                    impact_acknowledged=bool(form.impact_acknowledged.data),
                )
            except RoleDelegationError as exc:
                rollback_role_transaction()
                _permission_error(form, str(exc))
            except RoleImpactAcknowledgementRequired as exc:
                rollback_role_transaction()
                form.impact_acknowledged.errors = [*form.impact_acknowledged.errors, str(exc)]
            except RoleInputError as exc:
                rollback_role_transaction()
                form.name.errors = [*form.name.errors, str(exc)]
            except (SQLAlchemyError, ValueError):
                rollback_role_transaction()
                current_app.logger.exception('Failed to update custom role %s with submitted permissions.', role_id)
                role_access_feedback(
                    actor=actor,
                    event_type='rbac_role_update_failed',
                    status='error',
                    title='Custom role update failed',
                    message='No role changes were saved.',
                    role=role,
                    detail='Review the role configuration and permission selection, then try again.',
                )
            else:
                role_access_feedback(
                    actor=actor,
                    event_type='rbac_role_updated',
                    status='success',
                    title='Custom role updated',
                    message=f'{role.display_name} access scope was updated.',
                    role=role,
                    detail=f'{len(effective_permission_ids)} effective permissions are now assigned.',
                )
                return redirect(url_for('access.roles.index'))

    selected_permission_ids = expand_permission_ids(selected_permission_ids)
    return _render_role_form(
        form=form,
        actor=actor,
        role=role,
        clone_source=None,
        view_only=False,
        selected_permission_ids=selected_permission_ids,
    )


@bp.post('/<int:role_id>/delete')
@permission_required('roles.manage')
def delete(role_id: int):
    actor = cast(User, current_user._get_current_object())
    role = lock_role_for_mutation(role_id)
    if role is None:
        rollback_role_transaction()
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_delete_rejected',
            status='error',
            title='Role deletion unavailable',
            message='The requested role record was not found.',
        )
        return redirect(url_for('access.roles.index'))

    form = DeleteRoleForm()
    if not form.validate_on_submit() or str(form.role_id.data) != str(role.id):
        rollback_role_transaction()
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_delete_rejected',
            status='error',
            title='Role deletion rejected',
            message='The role deletion request could not be validated.',
            role=role,
        )
        return redirect(url_for('access.roles.index'))
    if role_is_mutation_protected(role):
        rollback_role_transaction()
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_delete_rejected',
            status='warning',
            title='Protected role cannot be deleted',
            message='Source-controlled or system-owned roles cannot be deleted from the Access workspace.',
            role=role,
        )
        return redirect(url_for('access.roles.index'))
    try:
        ensure_role_within_delegation_boundary(actor=actor, role=role)
    except RoleDelegationError as exc:
        rollback_role_transaction()
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_delete_rejected',
            status='warning',
            title='Role deletion exceeds delegation ceiling',
            message=str(exc),
            role=role,
        )
        return redirect(url_for('access.roles.index'))
    if not role_version_matches(role, form.role_version.data):
        rollback_role_transaction()
        role_access_feedback(
            actor=actor,
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
        rollback_role_transaction()
        blocker_parts = []
        if blockers['assigned_users']:
            blocker_parts.append(f'{blockers["assigned_users"]} user assignment(s)')
        if blockers['identity_providers']:
            blocker_parts.append(f'{blockers["identity_providers"]} identity provider default mapping(s)')
        role_access_feedback(
            actor=actor,
            event_type='rbac_role_delete_blocked',
            status='warning',
            title='Role deletion blocked',
            message='The custom role is still referenced by ' + ' and '.join(blocker_parts) + '.',
            role=role,
            detail='Remove the user and identity-provider mappings before deleting this role.',
        )
        return redirect(url_for('access.roles.index'))

    role_name = role.display_name
    role_snapshot = delete_custom_role(actor=actor, role=role)
    role_access_feedback(
        actor=actor,
        event_type='rbac_role_deleted',
        status='success',
        title='Custom role deleted',
        message=f'{role_name} was removed from the role registry.',
        role_snapshot=role_snapshot,
        detail='Historical administrative records remain available in Activity Audit Log.',
    )
    return redirect(url_for('access.roles.index'))
