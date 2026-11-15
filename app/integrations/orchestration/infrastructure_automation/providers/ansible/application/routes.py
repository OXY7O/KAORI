"""Ansible provider-owned Integration workspace; all GET state is committed."""

from __future__ import annotations

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.access.rbac.decorators import permission_required
from app.common.http import htmx_target, is_htmx_request
from app.common.pagination import paginate_query
from app.integrations.kernel.registry import get_integration
from app.integrations.orchestration.infrastructure_automation.providers.ansible import INTEGRATION_TYPE
from app.integrations.orchestration.infrastructure_automation.providers.ansible.application.service import (
    AnsibleConnectionForm,
    instance_or_none,
    jobs_query,
    parse_connection_form,
    save_connection,
)
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import record_operational_activity

ansible_bp = Blueprint('ansible', __name__, url_prefix='/integrations/orchestration/ansible')
TEMPLATE_ROOT = 'integrations/orchestration/infrastructure_automation/providers/ansible'


def _csrf_or_400() -> None:
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        abort(400)


def _notify(instance: IntegrationInstance | None, *, status: str, title: str, detail: str, event: str) -> None:
    record_operational_activity(
        user_id=int(current_user.id),
        event_type=event,
        status=status,
        title=title,
        message=detail,
        detail='Only worker localhost read-only facts are supported. External hosts remain unverified.',
        action_url=(
            url_for('ansible.instance_detail', instance_id=instance.id)
            if instance is not None
            else url_for('ansible.index')
        ),
        action_label='Open Ansible Connection' if instance is not None else 'Open Ansible Registry',
        action_icon='workflow',
        metadata={'integration_type': INTEGRATION_TYPE, 'integration_instance_id': instance.id if instance else None},
        queue_feedback=True,
        delivery_policy=OperationalDeliveryPolicy.DECK_ON_FAILURE,
    )


def _redirect(target: str) -> ResponseReturnValue:
    if is_htmx_request():
        response = make_response('', 204)
        response.headers['HX-Redirect'] = target
        return response
    return redirect(target)


@ansible_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    query_text = request.args.get('q', '').strip()[:120]
    status = request.args.get('status', 'all').strip().lower()
    if status not in {'all', 'enabled', 'disabled'}:
        status = 'all'
    query = IntegrationInstance.query.filter_by(integration_type=INTEGRATION_TYPE, provider_key='ansible')
    if query_text:
        query = query.filter(IntegrationInstance.name.ilike(f'%{query_text}%'))
    if status == 'enabled':
        query = query.filter(IntegrationInstance.enabled.is_(True))
    elif status == 'disabled':
        query = query.filter(IntegrationInstance.enabled.is_(False))
    rows, pagination = paginate_query(
        query.order_by(IntegrationInstance.name.asc(), IntegrationInstance.id.asc()),
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 5),
    )
    counts = {
        'total': IntegrationInstance.query.filter_by(integration_type=INTEGRATION_TYPE, provider_key='ansible').count(),
        'enabled': IntegrationInstance.query.filter_by(integration_type=INTEGRATION_TYPE, provider_key='ansible', enabled=True).count(),
    }
    context = {
        'rows': rows,
        'pagination': pagination,
        'query': query_text,
        'status_filter': status,
        'counts': counts,
    }
    if is_htmx_request() and htmx_target() == 'ansible-connections-registry':
        return render_template(f'{TEMPLATE_ROOT}/partials/_registry.html', **context)
    return render_template(f'{TEMPLATE_ROOT}/frontpage.html', **context)


def _render_form(
    *, instance: IntegrationInstance | None, form: AnsibleConnectionForm | None, error: str | None = None
) -> ResponseReturnValue:
    return render_template(
        f'{TEMPLATE_ROOT}/instance_form.html',
        instance=instance,
        form=form,
        error=error,
        source_commit=__import__('app.infrastructure_automation.source', fromlist=['SOURCE_SHA']).SOURCE_SHA,
    ), (400 if error else 200)


@ansible_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def new_instance() -> ResponseReturnValue:
    if request.method == 'GET':
        return _render_form(instance=None, form=None)
    _csrf_or_400()
    try:
        form = parse_connection_form(request.form)
        instance = save_connection(form)
    except ValueError as exc:
        return _render_form(instance=None, form=_safe_form_fallback(), error=str(exc))
    _notify(instance, status='success', title='Ansible connection registered', detail='Saved in the canonical Integration Registry; remote host readiness remains unverified.', event='ansible_connection_created')
    return _redirect(url_for('ansible.instance_detail', instance_id=instance.id))


def _safe_form_fallback() -> AnsibleConnectionForm:
    """Never echo or persist unrecognized secrets from rejected request fields."""
    return AnsibleConnectionForm(
        name=str(request.form.get('name') or '')[:120],
        description=str(request.form.get('description') or '')[:1000],
        environment=str(request.form.get('environment') or 'development')[:20],
        enabled=request.form.get('enabled') == 'on',
    )


@ansible_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def edit_instance(instance_id: int) -> ResponseReturnValue:
    instance = instance_or_none(instance_id)
    if instance is None:
        abort(404)
    if request.method == 'GET':
        return _render_form(instance=instance, form=None)
    _csrf_or_400()
    try:
        form = parse_connection_form(request.form)
        save_connection(form, instance=instance)
    except ValueError as exc:
        return _render_form(instance=instance, form=_safe_form_fallback(), error=str(exc))
    _notify(instance, status='success', title='Ansible connection updated', detail='Updated identity and lifecycle; readiness reset to Validation Required.', event='ansible_connection_updated')
    return _redirect(url_for('ansible.instance_detail', instance_id=instance.id))


def _job_context(instance_id: int) -> dict[str, object]:
    query = jobs_query(instance_id)
    rows, pagination = paginate_query(
        query,
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 5),
    )
    latest = query.first()
    return {'jobs': rows, 'jobs_pagination': pagination, 'latest': latest}


@ansible_bp.get('/instances/<int:instance_id>')
@permission_required('integrations.manage')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = instance_or_none(instance_id)
    if instance is None:
        abort(404)
    context = {'instance': instance, **_job_context(instance_id)}
    if is_htmx_request() and htmx_target() == 'ansible-jobs-section':
        return render_template(f'{TEMPLATE_ROOT}/partials/_jobs.html', **context)
    return render_template(f'{TEMPLATE_ROOT}/instance_detail.html', **context)


@ansible_bp.post('/instances/<int:instance_id>/probe')
@permission_required('integrations.manage')
def probe(instance_id: int) -> ResponseReturnValue:
    instance = instance_or_none(instance_id)
    if instance is None:
        abort(404)
    _csrf_or_400()
    try:
        job, created = get_integration(INTEGRATION_TYPE).execute(
            'host_facts.collect', instance, requested_by_user_id=int(current_user.id)
        )
    except Exception as exc:
        # Never expose source paths, Runner stderr, internal host identity or secrets.
        _notify(
            instance,
            status='warning',
            title='Worker localhost probe blocked',
            detail=f'No operation dispatched ({type(exc).__name__}). Check operator source/queue readiness.',
            event='ansible_localhost_probe_blocked',
        )
    else:
        _notify(
            instance,
            status='info',
            title='Worker localhost facts queued' if created else 'Existing localhost job retained',
            detail=f'Canonical JobExecution {job.public_id} — worker-local only, not remote host validation.',
            event='ansible_localhost_probe_queued' if created else 'ansible_localhost_probe_already_running',
        )
    return _redirect(url_for('ansible.instance_detail', instance_id=instance_id))
