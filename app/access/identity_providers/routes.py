from __future__ import annotations

from typing import cast

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app.access.authentication.identity_provider.adapters.ldap.client import ExternalProviderError
from app.access.authentication.identity_provider.browser import SsoProviderError
from app.access.authentication.identity_provider.catalog import (
    AuthProviderFamily,
    configurable_provider_definitions,
    provider_definition,
)
from app.access.authentication.identity_provider.configuration import (
    apply_identity_provider_configuration,
    validate_identity_provider,
)
from app.access.authentication.identity_provider.directory import DirectoryProviderError, ExternalIdentity
from app.access.authentication.identity_provider.registry import get_directory_provider_adapter
from app.access.authentication.sso import SsoAdmissionError
from app.access.identity_providers.forms import (
    ExternalIdentityProvisionForm,
    ExternalIdentitySearchForm,
    IdentityProviderForm,
    configuration_from_form,
    populate_form,
)
from app.access.identity_providers.notifications import identity_provider_feedback
from app.access.identity_providers.provisioning import (
    IdentityProjectionError,
    assign_projection_role_choices,
    assign_provider_choices,
    provision_external_identity,
)
from app.access.identity_providers.provisioning_proof import (
    ProjectionProofError,
    issue_projection_proof,
    verify_projection_proof,
)
from app.access.identity_providers.service import (
    assign_provider_role_choices,
    build_identity_provider_payload,
    normalize_provider_filters,
    provider_default_role_assignment_error,
)
from app.access.rbac.decorators import permission_required
from app.common.admin_audit import record_admin_event
from app.extensions.db import db
from app.models import IdentityProvider, User

bp = Blueprint('identity_providers', __name__, url_prefix='/access/identity-providers')


def _form_context(form: IdentityProviderForm, provider: IdentityProvider | None, **extra):
    selected_key = str(form.provider_key.data or (provider.provider_key if provider else '') or '').strip().lower()
    selected_definition = provider_definition(selected_key) if selected_key else None
    return {
        'form': form,
        'provider': provider,
        'provider_options': configurable_provider_definitions(),
        'selected_definition': selected_definition,
        **extra,
    }


@bp.get('/')
@permission_required('identity_providers.view')
def index():
    filters = normalize_provider_filters(request.args.to_dict())
    payload = build_identity_provider_payload(filters)
    payload['active_tab'] = 'providers' if request.args.get('tab') == 'providers' else 'overview'
    if request.headers.get('HX-Request') == 'true':
        return render_template('access/identity_providers/partials/_registry.html', **payload)
    return render_template('access/identity_providers/index.html', **payload)


@bp.route('/new', methods=['GET', 'POST'])
@permission_required('identity_providers.manage')
def create():
    actor = cast(User, current_user)
    form = IdentityProviderForm()
    assign_provider_role_choices(form, actor=actor)
    if form.validate_on_submit():
        role_error = provider_default_role_assignment_error(actor, form.default_role_id.data)
        if role_error:
            form.default_role_id.errors = [*form.default_role_id.errors, role_error]
            return render_template('access/identity_providers/form.html', **_form_context(form, None))
        provider = IdentityProvider()
        apply_identity_provider_configuration(provider, configuration_from_form(form))
        db.session.add(provider)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.key.errors = [*form.key.errors, 'Provider key already exists.']
        else:
            identity_provider_feedback(
                actor=actor,
                event_type='identity_provider_created',
                status='success',
                title='Identity provider created',
                message=f'{provider.display_name} configuration was created.',
                provider_id=provider.id,
                provider_key=provider.provider_key,
            )
            return redirect(url_for('identity_providers.index'))
    return render_template('access/identity_providers/form.html', **_form_context(form, None))


@bp.route('/<int:provider_id>/edit', methods=['GET', 'POST'])
@permission_required('identity_providers.manage')
def edit(provider_id: int):
    provider = db.get_or_404(IdentityProvider, provider_id)
    actor = cast(User, current_user)
    form = IdentityProviderForm()
    assign_provider_role_choices(form, actor=actor)
    if request.method == 'GET':
        populate_form(form, provider)
    if form.validate_on_submit():
        role_error = provider_default_role_assignment_error(actor, form.default_role_id.data)
        if role_error:
            form.default_role_id.errors = [*form.default_role_id.errors, role_error]
            return render_template('access/identity_providers/form.html', **_form_context(form, provider))
        apply_identity_provider_configuration(provider, configuration_from_form(form))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.key.errors = [*form.key.errors, 'Provider key already exists.']
        else:
            identity_provider_feedback(
                actor=actor,
                event_type='identity_provider_updated',
                status='success',
                title='Identity provider updated',
                message=f'{provider.display_name} configuration was updated.',
                provider_id=provider.id,
                provider_key=provider.provider_key,
            )
            return redirect(url_for('identity_providers.index'))
    return render_template('access/identity_providers/form.html', **_form_context(form, provider))


@bp.post('/test')
@bp.post('/<int:provider_id>/test')
@permission_required('identity_providers.manage')
def test_configuration(provider_id: int | None = None):
    provider = db.get_or_404(IdentityProvider, provider_id) if provider_id is not None else None
    actor = cast(User, current_user)
    form = IdentityProviderForm()
    assign_provider_role_choices(form, actor=actor)
    test_result: dict[str, str]
    if form.validate_on_submit():
        role_error = provider_default_role_assignment_error(actor, form.default_role_id.data)
        if role_error:
            form.default_role_id.errors = [*form.default_role_id.errors, role_error]
            return render_template('access/identity_providers/form.html', **_form_context(form, provider))
        candidate = IdentityProvider()
        apply_identity_provider_configuration(candidate, configuration_from_form(form))
        try:
            message = validate_identity_provider(candidate)
        except (ExternalProviderError, SsoProviderError, SsoAdmissionError) as exc:
            test_result = {'status': 'error', 'title': 'Connection Test Failed', 'message': str(exc)}
        else:
            test_result = {'status': 'success', 'title': 'Connection Test Passed', 'message': message}
    else:
        test_result = {
            'status': 'error',
            'title': 'Connection Test Blocked',
            'message': 'Complete the required provider fields before testing the current configuration.',
        }
    return render_template(
        'access/identity_providers/form.html', **_form_context(form, provider, test_result=test_result)
    )


@bp.post('/<int:provider_id>/validate')
@permission_required('identity_providers.manage')
def validate(provider_id: int):
    actor = cast(User, current_user)
    provider = db.get_or_404(IdentityProvider, provider_id)
    status, title = 'success', 'Provider validation passed'
    try:
        message = validate_identity_provider(provider)
    except (ExternalProviderError, SsoProviderError, SsoAdmissionError) as exc:
        status, title, message = 'error', 'Provider validation failed', str(exc)
    identity_provider_feedback(
        actor=actor,
        event_type='identity_provider_validated',
        status=status,
        title=title,
        message=message,
        provider_id=provider.id,
        provider_key=provider.provider_key,
    )
    return redirect(url_for('identity_providers.index'))


@bp.route('/directory-provisioning', methods=['GET', 'POST'])
@permission_required('identity_providers.provision')
def directory_provisioning():
    actor = cast(User, current_user)
    search_form = ExternalIdentitySearchForm()
    provision_form = ExternalIdentityProvisionForm()
    assign_provider_choices(search_form)
    assign_projection_role_choices(provision_form, actor=actor)
    results: list[ExternalIdentity] = []
    projection_proofs: dict[str, str] = {}
    selected_provider = None
    if search_form.validate_on_submit() and search_form.submit.data:
        selected_provider = db.session.get(IdentityProvider, search_form.provider_id.data)
        if selected_provider is not None:
            try:
                results = get_directory_provider_adapter(selected_provider.adapter_key).search(
                    selected_provider, search_form.query.data or ''
                )
                projection_proofs = {
                    identity.subject: issue_projection_proof(
                        provider_id=selected_provider.id,
                        identity=identity,
                        user_id=int(current_user.id),
                    )
                    for identity in results
                }
            except (ExternalProviderError, DirectoryProviderError) as exc:
                identity_provider_feedback(
                    actor=actor,
                    event_type='external_identity_search_failed',
                    status='error',
                    title='Directory search failed',
                    message=str(exc),
                    provider_id=selected_provider.id,
                    provider_key=selected_provider.provider_key,
                )
    return render_template(
        'access/identity_providers/directory_provisioning.html',
        search_form=search_form,
        provision_form=provision_form,
        results=results,
        selected_provider=selected_provider,
        projection_proofs=projection_proofs,
        active_tab='directory',
    )


@bp.post('/directory-provisioning/provision')
@permission_required('identity_providers.provision')
def provision_identity():
    actor = cast(User, current_user)
    form = ExternalIdentityProvisionForm()
    assign_projection_role_choices(form, actor=actor)
    if not form.validate_on_submit():
        identity_provider_feedback(
            actor=actor,
            event_type='external_identity_provision_failed',
            status='error',
            title='Provisioning failed',
            message='The external identity request was incomplete.',
        )
        return redirect(url_for('identity_providers.directory_provisioning'))

    provider_id_raw = (form.provider_id.data or '').strip()
    role_id = form.role_id.data
    if not provider_id_raw.isdigit() or role_id is None:
        return redirect(url_for('identity_providers.directory_provisioning'))

    provider = db.session.get(IdentityProvider, int(provider_id_raw))
    if (
        provider is None
        or not provider.enabled
        or provider_definition(provider.provider_key).family != AuthProviderFamily.DIRECTORY
    ):
        identity_provider_feedback(
            actor=actor,
            event_type='external_identity_provision_failed',
            status='error',
            title='Provisioning failed',
            message='The selected directory provider is unavailable.',
        )
        return redirect(url_for('identity_providers.directory_provisioning'))

    try:
        identity = verify_projection_proof(
            token=form.projection_proof.data or '',
            provider_id=provider.id,
            user_id=int(current_user.id),
        )
        user = provision_external_identity(
            actor=actor,
            provider=provider,
            identity=identity,
            role_id=role_id,
            is_active=bool(form.is_active.data),
        )
        record_admin_event(
            actor=actor,
            action='user.external_identity_provisioned',
            target=user,
            summary=f'Provisioned directory identity {user.username}.',
            metadata={'provider_key': provider.provider_key, 'provider_instance_key': provider.key},
        )
        db.session.commit()
    except (IdentityProjectionError, ProjectionProofError) as exc:
        db.session.rollback()
        identity_provider_feedback(
            actor=actor,
            event_type='external_identity_provision_failed',
            status='error',
            title='Provisioning failed',
            message=str(exc),
            provider_id=provider.id,
            provider_key=provider.provider_key,
        )
    else:
        identity_provider_feedback(
            actor=actor,
            event_type='external_identity_provisioned',
            status='success',
            title='Directory user provisioned',
            message=f'{user.username} can authenticate through {provider.display_name}.',
            provider_id=provider.id,
            provider_key=provider.provider_key,
        )
    return redirect(url_for('users.index'))
