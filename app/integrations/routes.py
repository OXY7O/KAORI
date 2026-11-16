from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.rbac.decorators import permission_required
from app.infrastructure_automation.kubernetes.plan_currentness import (
    committed_kubespray_plan_currentness,
)
from app.infrastructure_automation.kubernetes.plan_dispatch import (
    KubesprayPlanNotQualified,
    dispatch_kubespray_plan_review,
)
from app.common.http import htmx_target, is_htmx_request
from app.extensions.db import db
from app.integrations.binding_web import binding_response as _binding_response
from app.integrations.domain_service import (
    BindingRegistryFilters,
    ProviderRegistryFilters,
    build_integration_domain_page,
)
from app.integrations.observability.metrics_source.application.registration_web import (
    new_instance_response,
    test_new_instance_connection_response,
)
from app.integrations.observability.metrics_source.providers import provider_definitions
from app.integrations.orchestration.configuration_automation.frontpage import build_ansible_frontpage
from app.integrations.orchestration.configuration_automation.providers.ansible.preflight import (
    committed_kubespray_preflight,
)
from app.integrations.orchestration.configuration_automation.providers.ansible.forms import AnsibleSourceConnectionForm
from app.integrations.orchestration.configuration_automation.providers.ansible.proof import (
    issue_source_proof,
    verified_source_proof,
)
from app.integrations.orchestration.configuration_automation.providers.ansible.service import (
    bound_kubernetes_targets,
    connection_jobs,
    get_connection,
    save_source_connection,
    source_validation_posture,
)
from app.integrations.orchestration.container_orchestrator.frontpage import (
    KubernetesCoverageFilters,
    KubernetesFrontPageFilters,
    KubernetesRegistryFilters,
    build_kubernetes_page,
    build_kubernetes_registry_row,
)
from app.integrations.orchestration.container_orchestrator.tenant_capsule_web import capsule_rbac_operation
from app.integrations.overview_workspace import build_integrations_overview
from app.integrations.provider_matrix import provider_kinds
from app.integrations.repository import get_kubernetes_connection_by_cluster_id
from app.integrations.runtime.presentation import runtime_history_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.service import (
    MetricsSourceRegistryFilters,
    build_alertmanager_page,
    build_integration_runtime_detail,
    build_kubernetes_capability_registry,
    build_kubernetes_detail,
    build_metrics_source_page,
)
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    AutomationSourceRejected,
    verify_public_kubespray_source,
)
from app.integrations.taxonomy import get_domain_definition
from app.integrations.validation.state import (
    build_validation_snapshot,
    get_active_validation_task_id,
)
from app.integrations.validation.web import (
    enqueue_instance_validation,
    enqueue_runtime_health_refresh,
    snapshot_feedback_for_user,
    validate_snapshot_access,
    validation_poll_response,
)
from app.platform_operations.jobs.dispatcher import JobWorkerUnavailable
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')


@integrations_bp.get('/')
@permission_required('integrations.manage')
def overview() -> ResponseReturnValue:
    context = build_integrations_overview(
        tab=request.args.get('tab', 'catalog').strip(),
        integration_type=request.args.get('integration_type', '').strip(),
        health=request.args.get('health', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    is_runtime_partial = (
        is_htmx_request() and htmx_target() == 'integration-runtime-overview' and context['active_tab'] == 'runtime'
    )
    if is_runtime_partial:
        return render_template('integrations/partials/_runtime_overview.html', **context)
    return render_template('integrations/overview.html', **context)


def _render_domain_page(domain_key: str) -> ResponseReturnValue:
    is_workspace_partial = is_htmx_request() and htmx_target() == 'domain-workspace'
    context = build_integration_domain_page(
        domain_key,
        active_tab=request.args.get('tab', 'registry').strip(),
        provider_filters=ProviderRegistryFilters(
            query=request.args.get('provider_q', '').strip(),
            provider_key=request.args.get('provider_key', '').strip(),
            readiness=request.args.get('provider_readiness', '').strip(),
            page=request.args.get('provider_page', 1, type=int) or 1,
            per_page=request.args.get('provider_per_page', 5, type=int) or 5,
        ),
        binding_filters=BindingRegistryFilters(
            query=request.args.get('binding_q', '').strip(),
            provider=request.args.get('binding_provider', '').strip(),
            status=request.args.get('binding_status', '').strip(),
            page=request.args.get('binding_page', 1, type=int) or 1,
            per_page=request.args.get('binding_per_page', 5, type=int) or 5,
        ),
        include_capabilities=not is_workspace_partial,
    )
    if is_workspace_partial:
        return render_template('integrations/partials/_domain_workspace.html', **context)
    return render_template('integrations/domain.html', **context)


@integrations_bp.get('/orchestration')
@permission_required('integrations.manage')
def orchestration() -> ResponseReturnValue:
    return _render_domain_page('orchestration')


@integrations_bp.get('/ansible')
@permission_required('integrations.manage')
def ansible() -> ResponseReturnValue:
    """Connection-first Ansible provider landing backed by canonical state."""
    context = build_ansible_frontpage(
        query=request.args.get('q', '').strip()[:80],
        environment=request.args.get('environment', '').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    if is_htmx_request() and htmx_target() == 'ansible-connection-registry':
        return render_template(
            'integrations/orchestration/configuration_automation/providers/ansible/_connection_registry.html', **context
        )
    return render_template(
        'integrations/orchestration/configuration_automation/providers/ansible/frontpage.html', **context
    )


@integrations_bp.get('/ansible/profiles')
@permission_required('integrations.manage')
def ansible_choose() -> ResponseReturnValue:
    """Reusable automation profile selection; future profiles remain disabled."""
    return render_template('integrations/orchestration/configuration_automation/providers/ansible/choose.html')


def _ansible_registration_feedback(*, event_type: str, status: str, title: str, message: str) -> None:
    """Emit canonical toast/Audit; source checks must not spam Notification Deck."""
    record_operational_activity(
        user_id=int(current_user.id),
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        action_url=url_for('integrations.ansible_new_connection'),
        action_label='Review Ansible Source',
        action_icon='git-commit',
        metadata={'provider': 'ansible', 'registration_phase': 'source_only', 'feedback_delivery': 'toast'},
        queue_feedback=True,
        delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
    )


def _ansible_registration_validation_message(form: AnsibleSourceConnectionForm) -> str:
    """Return safe labels, never user-entered values or raw validation errors."""
    if 'csrf_token' in form.errors:
        return 'Form session expired. Reload the page and retry Validate Source.'
    labels = {
        'name': 'Connection Name',
        'environment': 'Environment',
        'description': 'Description',
        'profile_key': 'Automation Profile',
        'repository': 'Git Repository',
        'revision': 'Git Commit SHA',
        'ansible_core_version': 'Ansible Core Version',
        'ansible_runner_version': 'Ansible Runner Version',
        'kubespray_release': 'Kubespray Release',
        'execution_environment_digest': 'Execution Environment Digest',
    }
    invalid = [label for field, label in labels.items() if field in form.errors]
    if not invalid:
        return 'Review required fields before continuing.'
    visible = ', '.join(invalid[:3])
    suffix = f' (+{len(invalid) - 3} other fields)' if len(invalid) > 3 else ''
    return f'Review required fields: {visible}{suffix} before continuing.'


@integrations_bp.route('/ansible/connections/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def ansible_new_connection() -> ResponseReturnValue:
    """Register only after immutable Git source proof; use shared operational feedback."""
    form = AnsibleSourceConnectionForm()
    proof = ''
    if request.method == 'POST':
        action = str(request.form.get('action') or '').strip()
        if not form.validate_on_submit():
            _ansible_registration_feedback(
                event_type='ansible_source_registration_input_rejected',
                status='warning',
                title='Ansible Source Registration Needs Attention',
                message=_ansible_registration_validation_message(form),
            )
        elif action not in {'test', 'save'}:
            _ansible_registration_feedback(
                event_type='ansible_source_registration_action_rejected',
                status='warning',
                title='Ansible Registration Action Rejected',
                message='Use Validate Source before saving this connection.',
            )
        else:
            try:
                values = form.to_input()
            except ValueError:
                _ansible_registration_feedback(
                    event_type='ansible_source_registration_policy_rejected',
                    status='warning',
                    title='Ansible Source Policy Rejected',
                    message='The automation profile, Git source or version does not match the reviewed candidate.',
                )
            else:
                if action == 'test':
                    try:
                        evidence = verify_public_kubespray_source(values.repository, values.revision)
                        proof = issue_source_proof(values, evidence, int(current_user.id))
                    except (AutomationSourceRejected, ValueError):
                        _ansible_registration_feedback(
                            event_type='ansible_source_validation_failed',
                            status='error',
                            title='Ansible Source Validation Failed',
                            message='Unable to verify the reviewed Git source. Check the approved revision and retry.',
                        )
                    else:
                        _ansible_registration_feedback(
                            event_type='ansible_source_validation_checked',
                            status='success',
                            title='Ansible Source Validated',
                            message='Git objects and version policy match the reviewed candidate. '
                            'Host and cluster readiness remain blocked.',
                        )
                else:
                    evidence = verified_source_proof(
                        str(form.source_test_proof.data or ''), values, int(current_user.id)
                    )
                    if evidence is None:
                        _ansible_registration_feedback(
                            event_type='ansible_source_registration_proof_rejected',
                            status='warning',
                            title='Ansible Source Verification Required',
                            message='Re-run Validate Source after changes; a current proof is required to register.',
                        )
                    else:
                        try:
                            connection = save_source_connection(values, evidence=evidence)
                        except SQLAlchemyError:
                            current_app.logger.exception('Ansible source connection registration failed.')
                            _ansible_registration_feedback(
                                event_type='ansible_source_registration_failed',
                                status='error',
                                title='Ansible Source Registration Failed',
                                message='Unable to commit the connection. Review the registry and retry.',
                            )
                        except ValueError as exc:
                            duplicate = str(exc) == 'An automation connection with this name already exists.'
                            _ansible_registration_feedback(
                                event_type='ansible_source_registration_rejected',
                                status='warning',
                                title='Ansible Source Registration Rejected',
                                message=(
                                    'An automation connection with this name already exists. Choose another name.'
                                    if duplicate
                                    else 'Registration was rejected by the reviewed source policy. '
                                    'Run Validate Source again.'
                                ),
                            )
                        else:
                            record_operational_activity(
                                user_id=int(current_user.id),
                                event_type='ansible_source_connection_registered',
                                status='success',
                                title='Ansible Source Connection Registered',
                                message='Git source was checked; remote execution and provider readiness are not enabled.',
                                action_url=url_for('integrations.ansible_connection_detail', instance_id=connection.id),
                                action_label='Open Ansible Connection',
                                action_icon='workflow',
                                metadata={'provider': 'ansible', 'instance_id': connection.id},
                                queue_feedback=True,
                            )
                            return redirect(url_for('integrations.ansible_connection_detail', instance_id=connection.id))
    return render_template(
        'integrations/orchestration/configuration_automation/providers/ansible/form.html',
        form=form,
        source_test_proof=proof,
        notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
    )


@integrations_bp.get('/ansible/connections/<int:instance_id>')
@permission_required('integrations.manage')
def ansible_connection_detail(instance_id: int) -> ResponseReturnValue:
    """Four reusable provider tabs; only committed facts, no host/provider calls."""
    connection = get_connection(instance_id)
    if connection is None:
        abort(404)
    jobs, pagination = connection_jobs(
        connection,
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    inventory_targets, inventory_pagination = bound_kubernetes_targets(
        connection,
        page=request.args.get('inventory_page', 1, type=int) or 1,
        per_page=request.args.get('inventory_per_page', 5, type=int) or 5,
    )
    template = (
        'integrations/orchestration/configuration_automation/providers/ansible/_detail_inventory.html'
        if is_htmx_request() and htmx_target() == 'ansible-inventory-registry'
        else 'integrations/orchestration/configuration_automation/providers/ansible/detail.html'
    )
    preflight = committed_kubespray_preflight(connection)
    return render_template(
        template,
        connection=connection,
        source=connection.metadata_json or {},
        source_posture=source_validation_posture(connection),
        kubespray_preflight=preflight.presentation(),
        kubespray_plan_currentness=committed_kubespray_plan_currentness(
            connection, preflight=preflight
        ).presentation(),
        can_generate_review_plan=bool(
            connection.enabled and getattr(current_user, 'has_permission', lambda _: False)('jobs.execute')
        ),
        jobs=jobs,
        pagination=pagination,
        inventory_targets=inventory_targets,
        inventory_pagination=inventory_pagination,
    )


@integrations_bp.post('/ansible/connections/<int:instance_id>/plan-review')
@permission_required('integrations.manage')
@permission_required('jobs.execute')
def ansible_plan_review(instance_id: int) -> ResponseReturnValue:
    """Dispatch only DB-backed, non-mutating Plan review; no Kubernetes Run."""
    connection = get_connection(instance_id)
    if connection is None:
        abort(404)
    try:
        validate_csrf(str(request.form.get('csrf_token') or ''))
    except ValidationError:
        abort(400)

    try:
        job, created = dispatch_kubespray_plan_review(connection, user_id=int(current_user.id))
    except (KubesprayPlanNotQualified, JobWorkerUnavailable):
        status = 'warning'
        event_type = 'ansible_kubespray_plan_review_blocked'
        title = 'Kubespray Plan Review Blocked'
        message = 'Source, host preflight or plan worker is not qualified. No operation was dispatched.'
    except SQLAlchemyError:
        current_app.logger.exception('Kubespray Plan review dispatch failed.')
        status = 'error'
        event_type = 'ansible_kubespray_plan_review_failed'
        title = 'Kubespray Plan Review Failed'
        message = 'Unable to record the review-only Plan job. No cluster mutation was authorized.'
    else:
        status = 'info'
        event_type = 'ansible_kubespray_plan_review_queued'
        title = 'Kubespray Plan Review Queued'
        message = (
            ('Review-only Plan is queued in Jobs & Executions; independent approval '
             'and cluster operations remain blocked.')
            if created
            else 'A review-only Plan job already exists; no duplicate dispatch was created.'
        )
        # No JobExecution identifier or secret is needed in toast metadata.
        del job

    record_operational_activity(
        user_id=int(current_user.id),
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        action_url=url_for('integrations.ansible_connection_detail', instance_id=connection.id) + '#runtime',
        action_label='Review Jobs',
        action_icon='clipboard-list',
        metadata={'provider': 'ansible', 'instance_id': connection.id, 'feedback_delivery': 'toast'},
        queue_feedback=True,
        delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
    )
    return redirect(url_for('integrations.ansible_connection_detail', instance_id=connection.id) + '#validation')


@integrations_bp.post('/ansible/connections/<int:instance_id>/validate-source')
@permission_required('integrations.manage')
def ansible_revalidate_source(instance_id: int) -> ResponseReturnValue:
    """Re-read only approved GitHub objects; never execute Ansible or probe hosts."""
    from flask_login import current_user

    connection = get_connection(instance_id)
    if connection is None:
        abort(404)
    try:
        validate_csrf(str(request.form.get('csrf_token') or ''))
    except ValidationError:
        abort(400)
    values = connection.metadata_json or {}
    try:
        evidence = verify_public_kubespray_source(
            str(values.get('source_repository') or ''), str(values.get('source_sha') or '')
        )
    except AutomationSourceRejected:
        connection.readiness_status = 'validation_required'
        connection.health_status = None
        connection.metadata_json = {
            **values,
            'source_validation': {
                'status': 'blocked',
                'operation_authorized': False,
                'checked_files': 0,
            },
            'execution_enabled': False,
            'mutation_authorized': False,
        }
        db.session.commit()
        state = 'warning'
        message = 'Pinned source could not be reverified. Remote execution remains blocked.'
    else:
        connection.metadata_json = {
            **values,
            'source_validation': evidence.as_dict(),
            'execution_enabled': False,
            'mutation_authorized': False,
        }
        connection.readiness_status = 'validation_required'
        connection.health_status = None
        db.session.commit()
        state = 'success'
        message = 'Git source files reverified. Host access and execution remain blocked.'
    record_operational_activity(
        user_id=int(current_user.id),
        event_type='ansible_source_revalidated',
        status=state,
        title='Ansible Source Validation',
        message=message,
        action_url=url_for('integrations.ansible_connection_detail', instance_id=connection.id) + '#validation',
        action_label='Review Validation',
        action_icon='scan-search',
        metadata={'provider': 'ansible', 'instance_id': connection.id},
        queue_feedback=True,
    )
    return redirect(url_for('integrations.ansible_connection_detail', instance_id=connection.id) + '#validation')


@integrations_bp.get('/observability')
@permission_required('integrations.manage')
def observability() -> ResponseReturnValue:
    return _render_domain_page('observability')


@integrations_bp.get('/storage')
@permission_required('integrations.manage')
def storage() -> ResponseReturnValue:
    return _render_domain_page('storage')


@integrations_bp.get('/registry')
@permission_required('integrations.manage')
def registry() -> ResponseReturnValue:
    return _render_domain_page('registry')


@integrations_bp.get('/secrets-management')
@permission_required('integrations.manage')
def secrets_management() -> ResponseReturnValue:
    return _render_domain_page('secrets_management')


@integrations_bp.get('/source-control')
@permission_required('integrations.manage')
def source_control() -> ResponseReturnValue:
    return _render_domain_page('source_control')


# The provider matrix defines which implementations may register; destinations
# remain provider-owned routes, never a second KAORI registration implementation.
_PROVIDER_REGISTRATION_ENDPOINTS = {
    ('container_orchestrator', 'kubernetes'): 'cluster.add_cluster',
    ('configuration_automation', 'ansible'): 'integrations.ansible_choose',
    ('alert_source', 'alertmanager'): 'alertmanager.new_instance',
    ('object_storage', 'minio'): 'minio.new_instance',
    ('registry', 'harbor'): 'harbor.new_instance',
    ('secrets_pki', 'vault'): 'vault.new_instance',
    ('source_control', 'github'): 'github_source.new_connection',
}


@integrations_bp.get('/providers/<string:integration_type>')
@permission_required('integrations.manage')
def choose_integration_provider(integration_type: str) -> ResponseReturnValue:
    """Select an admitted provider before entering its owned registration form."""
    if integration_type == 'metrics_source':
        return redirect(url_for('integrations.select_metrics_source_provider'))

    kinds = sorted(provider_kinds(integration_type), key=lambda kind: (not kind.available, kind.label.casefold()))
    if not kinds:
        abort(404)

    domain = get_domain_definition(kinds[0].domain_key)
    providers = [
        {
            'key': kind.key,
            'label': kind.label,
            'adapter': (
                'Not implemented'
                if kind.adapter_key == 'not_implemented'
                else kind.adapter_key.replace('_', ' ').title()
            ),
            'protocol': ('Not defined' if kind.protocol == 'not_defined' else kind.protocol.replace('_', ' ').upper()),
            'lifecycle': kind.lifecycle,
            'available': kind.available,
            'registration_url': (
                url_for(_PROVIDER_REGISTRATION_ENDPOINTS[(kind.integration_type, kind.key)])
                if kind.available and (kind.integration_type, kind.key) in _PROVIDER_REGISTRATION_ENDPOINTS
                else None
            ),
        }
        for kind in kinds
    ]
    return render_template(
        'integrations/provider_selector.html',
        domain=domain,
        integration_type=integration_type,
        providers=providers,
        available_count=sum(bool(provider['registration_url']) for provider in providers),
    )


@integrations_bp.get('/runtime/<string:detail_key>/details')
@permission_required('integrations.manage')
def runtime_overview_details(detail_key: str) -> ResponseReturnValue:
    integration_type, separator, instance_id = detail_key.partition(':')
    if not separator or not integration_type or not instance_id:
        abort(404)
    detail = build_integration_runtime_detail(integration_type, instance_id)
    if detail is None:
        abort(404)
    return render_template(
        'integrations/partials/_runtime_overview_modal.html',
        detail=detail,
    )


@integrations_bp.get('/kubernetes')
@permission_required('integrations.manage')
def kubernetes() -> ResponseReturnValue:
    context = build_kubernetes_page(
        KubernetesFrontPageFilters(
            registry=KubernetesRegistryFilters(
                query=request.args.get('q', '').strip(),
                environment=request.args.get('environment', '').strip(),
                readiness=request.args.get('readiness', '').strip(),
                coverage=request.args.get('coverage', '').strip(),
                page=request.args.get('page', 1, type=int) or 1,
                per_page=request.args.get('per_page', 5, type=int) or 5,
            ),
            coverage=KubernetesCoverageFilters(
                query=request.args.get('coverage_q', '').strip(),
                environment=request.args.get('coverage_environment', '').strip(),
                status=request.args.get('coverage_status', '').strip(),
                page=request.args.get('coverage_page', 1, type=int) or 1,
                per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
            ),
        )
    )
    requested_tab = request.args.get('tab', 'coverage').strip()
    context['active_tab'] = requested_tab if requested_tab in {'coverage', 'registry'} else 'coverage'
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'kubernetes-integration-coverage':
            return render_template(
                'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_integration_coverage.html',
                **context,
            )
        if target == 'kubernetes-connection-registry':
            return render_template(
                'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry.html',
                **context,
            )
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/frontpage.html', **context
    )


def _kubernetes_detail_context(
    cluster_id: str,
    *,
    include_history: bool = False,
    history_page: int | None = None,
    history_per_page: int | None = None,
) -> dict[str, object]:
    context = build_kubernetes_detail(
        cluster_id,
        binding_page=request.args.get('binding_page', 1, type=int) or 1,
        binding_per_page=request.args.get('binding_per_page', 5, type=int) or 5,
    )
    if context is None:
        abort(404)
    connection = context['connection']
    capability_task_id = get_active_validation_task_id(
        integration_type='container_orchestrator',
        operation='full_validation',
        integration_instance_id=connection.integration_instance_id,
    )
    runtime_task_id = get_active_validation_task_id(
        integration_type='container_orchestrator',
        operation='runtime_refresh',
        integration_instance_id=connection.integration_instance_id,
    )
    context['capability_validation_job'] = build_validation_snapshot(capability_task_id) if capability_task_id else None
    context['runtime_validation_job'] = build_validation_snapshot(runtime_task_id) if runtime_task_id else None
    context['capsule_rbac_bootstrap'] = capsule_rbac_operation('latest_capsule_role_bootstrap_evidence')(cluster_id)
    context['capability_registry'] = build_kubernetes_capability_registry(
        context['feature_rows'],
        query=request.args.get('capability_q', '').strip(),
        requirement=request.args.get('capability_requirement', '').strip(),
        status=request.args.get('capability_status', '').strip(),
        page=request.args.get('capability_page', 1, type=int) or 1,
        per_page=request.args.get('capability_per_page', 5, type=int) or 5,
    )
    if include_history:
        resolved_page = history_page if history_page is not None else (request.args.get('page', 1, type=int) or 1)
        resolved_per_page = (
            history_per_page if history_per_page is not None else (request.args.get('per_page', 5, type=int) or 5)
        )
        rows, pagination = paginate_runtime_history(
            'container_orchestrator',
            str(connection.id),
            page=resolved_page,
            per_page=resolved_per_page,
            trigger_type=request.args.get('history_trigger', '').strip(),
            health_status=request.args.get('history_health', '').strip(),
            readiness=request.args.get('history_readiness', '').strip(),
        )
        context['history'] = runtime_history_view(rows, pagination=pagination)
    return context


@integrations_bp.get('/kubernetes/<string:cluster_id>/bindings/registry')
@permission_required('clusters.view')
def kubernetes_binding_registry(cluster_id: str) -> ResponseReturnValue:
    context = _kubernetes_detail_context(cluster_id)
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_binding_registry.html',
        **context,
    )


@integrations_bp.get('/kubernetes/<string:cluster_id>/registry-details')
@permission_required('integrations.manage')
def kubernetes_registry_details(cluster_id: str) -> ResponseReturnValue:
    row = build_kubernetes_registry_row(cluster_id)
    if row is None:
        abort(404)
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_registry_detail_content.html',
        row=row,
    )


@integrations_bp.get('/kubernetes/<string:cluster_id>')
@permission_required('clusters.view')
def kubernetes_detail(cluster_id: str) -> ResponseReturnValue:
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html',
        **_kubernetes_detail_context(cluster_id, include_history=True),
    )


def _capsule_rbac_feedback_response(
    cluster_id: str,
    result: dict[str, object],
    *,
    operation: str,
) -> ResponseReturnValue:
    """Present committed Capsule RBAC evidence using the canonical KAORI feedback channel."""
    provider_status = str(result.get('status') or 'failed')
    if operation == 'check':
        summary = {
            'ready': (
                'Capsule RBAC check complete',
                'All four canonical ClusterRoles match their approved Access Profiles.',
            ),
            'missing': (
                'Capsule RBAC prerequisites missing',
                'One or more canonical ClusterRoles are missing; review the evidence before approved bootstrap.',
            ),
            'conflict': (
                'Capsule RBAC role conflict',
                'Existing ClusterRoles conflict with the approved profiles; no roles were changed.',
            ),
        }
        title, message = summary.get(
            provider_status,
            ('Capsule RBAC check failed', 'ClusterRole inspection did not complete; review the committed evidence.'),
        )
    else:
        title, message = (
            (
                'Capsule ClusterRole bootstrap verified',
                'Missing canonical ClusterRoles were created and verified.',
            )
            if provider_status == 'ready'
            else (
                'Capsule ClusterRole bootstrap needs attention',
                'ClusterRole bootstrap did not verify as Ready; inspect committed evidence before retrying.',
            )
        )
    feedback_status = (
        'success' if provider_status == 'ready' else 'warning' if provider_status == 'missing' else 'error'
    )
    destination = url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation'
    is_htmx = is_htmx_request()
    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type=f'kubernetes_capsule_rbac_{operation}',
        status=feedback_status,
        title=title,
        message=message,
        detail=(
            'ClusterRole inspection and bootstrap evidence is committed separately. '
            'Capsule controller bindings and effective Access Grants remain independent.'
        ),
        action_url=destination,
        action_label='Review Capsule RBAC evidence',
        action_icon='shield-check',
        metadata={
            'cluster_id': cluster_id,
            'operation': operation,
            'provider_status': provider_status,
            'ready': result.get('ready'),
            'missing': result.get('missing'),
            'conflict': result.get('conflict'),
            'source': 'capsule_cluster_rbac',
        },
        queue_feedback=not is_htmx,
        delivery_policy=OperationalDeliveryPolicy.DECK_ON_FAILURE,
    )
    if is_htmx:
        context = _kubernetes_detail_context(cluster_id)
        context.update(
            {
                'operation_feedback': feedback,
                'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
            }
        )
        return render_template(
            'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capsule_rbac_bootstrap.html',
            **context,
        )
    return redirect(destination)


@integrations_bp.post('/kubernetes/<string:cluster_id>/capsule-rbac/check')
@permission_required('clusters.sync')
def kubernetes_capsule_rbac_check(cluster_id: str) -> ResponseReturnValue:
    if get_kubernetes_connection_by_cluster_id(cluster_id) is None:
        abort(404)
    try:
        validate_csrf(str(request.form.get('csrf_token') or ''))
    except ValidationError:
        abort(400)
    result = capsule_rbac_operation('check_capsule_role_bootstrap')(cluster_id, int(current_user.id))
    return _capsule_rbac_feedback_response(cluster_id, result, operation='check')


@integrations_bp.post('/kubernetes/<string:cluster_id>/capsule-rbac/bootstrap')
@permission_required('clusters.manage')
@permission_required('integrations.manage')
def kubernetes_capsule_rbac_bootstrap(cluster_id: str) -> ResponseReturnValue:
    if get_kubernetes_connection_by_cluster_id(cluster_id) is None:
        abort(404)
    try:
        validate_csrf(str(request.form.get('csrf_token') or ''))
    except ValidationError:
        abort(400)
    if request.form.get('confirm_cluster_rbac') != 'approved':
        abort(400)
    result = capsule_rbac_operation('bootstrap_missing_capsule_roles')(cluster_id, int(current_user.id), approved=True)
    return _capsule_rbac_feedback_response(cluster_id, result, operation='bootstrap')


@integrations_bp.get('/kubernetes/<string:cluster_id>/capabilities/registry')
@permission_required('clusters.view')
def kubernetes_capability_registry(cluster_id: str) -> ResponseReturnValue:
    context = _kubernetes_detail_context(cluster_id)
    return render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_registry.html',
        validation_job=context.get('capability_validation_job'),
        **context,
    )


@integrations_bp.post('/kubernetes/<string:cluster_id>/capabilities/validate')
@permission_required('clusters.sync')
def kubernetes_capability_validate(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        validation_job, created = enqueue_instance_validation(
            integration_type='container_orchestrator',
            integration_instance_id=connection.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_capability_validation_queued'
            if created
            else 'kubernetes_capability_validation_already_running',
            status='info' if created else 'warning',
            title='Kubernetes capability validation queued' if created else 'Kubernetes validation already running',
            message=(
                f'KAORI queued full capability validation for {connection.cluster.name}.'
                if created
                else f'A Kubernetes validation job is already running for {connection.cluster.name}.'
            ),
            detail=(
                'The dedicated validation worker will discover served APIs, effective RBAC, stable adapters, and fallback requirements.'
                if created
                else 'KAORI retained the active worker task and did not enqueue a duplicate validation job.'
            ),
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation',
            action_label='Review capability validation',
            action_icon='scan-search',
            metadata={
                'task_id': validation_job.get('task_id'),
                'cluster_id': cluster_id,
                'connection_id': connection.id,
                'queue': current_app.config.get('INTEGRATION_VALIDATION_CELERY_QUEUE', 'integration-validation'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_capability_validation_enqueue_failed',
            status='error',
            title='Kubernetes capability validation not queued',
            message=f'KAORI could not queue capability validation for {connection.cluster.name}.',
            detail='Verify Redis, the Celery broker, and the integration-validation worker before retrying.',
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation',
            action_label='Review capability validation',
            action_icon='scan-search',
            metadata={'cluster_id': cluster_id, 'connection_id': connection.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        context = _kubernetes_detail_context(cluster_id)
        context.update(
            {
                'validation_job': validation_job,
                'capability_validation_job': validation_job,
                'operation_feedback': feedback,
                'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
            }
        )
        return render_template(
            'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html',
            **context,
        )
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation')


@integrations_bp.get('/kubernetes/<string:cluster_id>/capabilities/validate/status/<string:task_id>')
@permission_required('clusters.view')
def kubernetes_capability_validation_status(cluster_id: str, task_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='container_orchestrator',
        integration_instance_id=connection.integration_instance_id,
    ):
        abort(404)
    context = _kubernetes_detail_context(cluster_id)
    context.update(
        {
            'validation_job': snapshot,
            'capability_validation_job': snapshot,
            'operation_feedback': snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
            'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
            'runtime_history_oob': True,
        }
    )
    content = render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html',
        **context,
    )
    return validation_poll_response(content, snapshot=snapshot)


@integrations_bp.post('/kubernetes/<string:cluster_id>/runtime/refresh')
@permission_required('clusters.sync')
def kubernetes_runtime_refresh(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        validation_job, created = enqueue_runtime_health_refresh(
            integration_type='container_orchestrator',
            integration_instance_id=connection.integration_instance_id,
            requested_by_user_id=int(current_user.id),
        )
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_runtime_refresh_queued' if created else 'kubernetes_runtime_refresh_already_running',
            status='info' if created else 'warning',
            title='Kubernetes runtime refresh queued' if created else 'Kubernetes runtime refresh already running',
            message=(
                f'KAORI queued a lightweight runtime health refresh for {connection.cluster.name}.'
                if created
                else f'A validation or runtime refresh is already running for {connection.cluster.name}.'
            ),
            detail=(
                'The dedicated runtime worker will check reachability and runtime health while preserving full capability evidence.'
                if created
                else 'KAORI kept the existing task and did not enqueue a duplicate validation job.'
            ),
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime',
            action_label='Review Kubernetes runtime',
            action_icon='activity',
            metadata={
                'task_id': validation_job.get('task_id'),
                'cluster_id': cluster_id,
                'connection_id': connection.id,
                'queue': current_app.config.get('INTEGRATION_RUNTIME_CELERY_QUEUE', 'integration-runtime'),
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        validation_job = None
        feedback = record_operational_activity(
            user_id=int(current_user.id),
            event_type='kubernetes_runtime_refresh_enqueue_failed',
            status='error',
            title='Kubernetes runtime refresh not queued',
            message=f'KAORI could not queue runtime health refresh for {connection.cluster.name}.',
            detail='Verify Redis, the Celery broker, and the integration-runtime worker before retrying.',
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime',
            action_label='Review Kubernetes runtime',
            action_icon='activity',
            metadata={'cluster_id': cluster_id, 'connection_id': connection.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        context = _kubernetes_detail_context(cluster_id, include_history=True)
        context.update(
            {
                'validation_job': validation_job,
                'runtime_validation_job': validation_job,
                'operation_feedback': feedback,
                'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
                'runtime_history_oob': True,
            }
        )
        return render_template(
            'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html',
            **context,
        )
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#runtime')


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/refresh/status/<string:task_id>')
@permission_required('clusters.view')
def kubernetes_runtime_refresh_status(cluster_id: str, task_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    snapshot = build_validation_snapshot(task_id)
    if not validate_snapshot_access(
        snapshot,
        integration_type='container_orchestrator',
        integration_instance_id=connection.integration_instance_id,
    ):
        abort(404)
    context = _kubernetes_detail_context(cluster_id, include_history=True)
    context.update(
        {
            'validation_job': snapshot,
            'runtime_validation_job': snapshot,
            'operation_feedback': snapshot_feedback_for_user(snapshot, user_id=int(current_user.id)),
            'notification_context': get_navigation_notification_context(user_id=int(current_user.id)),
        }
    )
    content = render_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html',
        **context,
    )
    return validation_poll_response(content, snapshot=snapshot)


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/history')
@permission_required('clusters.view')
def kubernetes_runtime_history(cluster_id: str) -> ResponseReturnValue:
    connection = get_kubernetes_connection_by_cluster_id(cluster_id)
    if connection is None:
        abort(404)
    rows, pagination = paginate_runtime_history(
        'container_orchestrator',
        str(connection.id),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
        trigger_type=request.args.get('history_trigger', '').strip(),
        health_status=request.args.get('history_health', '').strip(),
        readiness=request.args.get('history_readiness', '').strip(),
    )
    return render_template(
        'integrations/partials/_runtime_history.html',
        runtime_history=runtime_history_view(rows, pagination=pagination),
        runtime_history_id='kubernetes-runtime-history',
        runtime_history_loading_id='kubernetes-history-loading',
        runtime_history_url=url_for('integrations.kubernetes_runtime_history', cluster_id=cluster_id),
        runtime_history_endpoint='integrations.kubernetes_runtime_history',
        runtime_history_route_args={'cluster_id': cluster_id},
        runtime_history_detail_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id),
        runtime_history_detail_endpoint='integrations.kubernetes_detail',
        runtime_history_filters_enabled=True,
        provider_label='Kubernetes',
    )


@integrations_bp.get('/observability/metrics-sources/new')
@permission_required('integrations.manage')
def select_metrics_source_provider() -> ResponseReturnValue:
    # Keep provider-specific capability definitions authoritative while reusing
    # the same admitted/planned registration contract as other Integrations.
    admitted_kinds = {kind.key: kind for kind in provider_kinds('metrics_source')}
    providers = [
        {
            'key': provider.key,
            'label': provider.label,
            'description': provider.description,
            'icon': provider.icon,
            'adapter_key': provider.adapter_key,
            'query_language': provider.query_language,
            'adapter': provider.adapter_key.replace('_', ' ').title(),
            'protocol': provider.query_language.upper(),
            'secondary_label': 'Query Language',
            'lifecycle': admitted_kinds[provider.key].lifecycle,
            'registration_url': (
                url_for('integrations.register_metrics_source', provider_key=provider.key)
                if admitted_kinds[provider.key].available
                else None
            ),
        }
        for provider in provider_definitions()
    ]
    return render_template(
        'integrations/observability/metrics_source/provider_selector.html',
        domain=get_domain_definition('observability'),
        integration_type='metrics_source',
        providers=providers,
        available_count=sum(bool(provider['registration_url']) for provider in providers),
        guide_title='Metrics Provider Selection',
        guide_text=(
            'Metrics adapters define protocol, query language, validation and query horizon. '
            'KAORI manages connection evidence and qualified consumer routing.'
        ),
    )


@integrations_bp.route('/observability/metrics-sources/<string:provider_key>/new', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def register_metrics_source(provider_key: str) -> ResponseReturnValue:
    return new_instance_response(provider_key=provider_key)


@integrations_bp.post('/observability/metrics-sources/<string:provider_key>/test-connection')
@permission_required('integrations.manage')
def test_metrics_source(provider_key: str) -> ResponseReturnValue:
    return test_new_instance_connection_response(provider_key=provider_key)


@integrations_bp.get('/observability/metrics-sources')
@permission_required('integrations.manage')
def metrics_sources() -> ResponseReturnValue:
    context = build_metrics_source_page(
        filters=MetricsSourceRegistryFilters(
            query=request.args.get('q', '').strip(),
            provider_key=request.args.get('provider_key', '').strip(),
            compatibility=request.args.get('compatibility', '').strip(),
            readiness=request.args.get('readiness', '').strip(),
            page=request.args.get('page', 1, type=int) or 1,
            per_page=request.args.get('per_page', 5, type=int) or 5,
        ),
        tab=request.args.get('tab', 'coverage').strip(),
        coverage_query=request.args.get('coverage_q', '').strip(),
        coverage_environment=request.args.get('coverage_environment', '').strip(),
        coverage_status=request.args.get('coverage_status', '').strip(),
        coverage_page=request.args.get('coverage_page', 1, type=int) or 1,
        coverage_per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'integration-coverage':
            return render_template('integrations/partials/_coverage_card.html', **context)
        if target == 'metrics-source-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
        if target == 'metrics-source-inventory-card':
            return render_template(
                'integrations/observability/metrics_source/partials/_instance_inventory.html', **context
            )
        return render_template('integrations/observability/metrics_source/partials/_inventory_content.html', **context)
    return render_template('integrations/observability/metrics_source/frontpage.html', **context)


@integrations_bp.get('/alertmanager')
@permission_required('integrations.manage')
def alertmanager() -> ResponseReturnValue:
    context = build_alertmanager_page(
        query=request.args.get('q', '').strip(),
        compatibility=request.args.get('compatibility', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        tab=request.args.get('tab', 'coverage').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
        coverage_query=request.args.get('coverage_q', '').strip(),
        coverage_environment=request.args.get('coverage_environment', '').strip(),
        coverage_status=request.args.get('coverage_status', '').strip(),
        coverage_page=request.args.get('coverage_page', 1, type=int) or 1,
        coverage_per_page=request.args.get('coverage_per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'integration-coverage':
            return render_template('integrations/partials/_coverage_card.html', **context)
        if target == 'alertmanager-coverage-content':
            return render_template('integrations/partials/_coverage_content.html', **context)
        if target == 'alertmanager-inventory-card':
            return render_template(
                'integrations/observability/alert_source/providers/alertmanager/partials/_inventory_card.html',
                **context,
            )
        return render_template(
            'integrations/observability/alert_source/providers/alertmanager/partials/_inventory_content.html', **context
        )
    return render_template('integrations/observability/alert_source/providers/alertmanager/frontpage.html', **context)


@integrations_bp.route('/metrics-sources/bind', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def bind_metrics_source() -> ResponseReturnValue:
    scope_key = request.values.get('scope_key', '').strip()
    if not scope_key:
        abort(400)
    return _binding_response('metrics_source', scope_key=scope_key)


@integrations_bp.route('/alertmanager/bind', methods=['GET', 'POST'])
@permission_required('integrations.manage')
def bind_alertmanager_source() -> ResponseReturnValue:
    scope_key = request.values.get('scope_key', '').strip()
    if not scope_key:
        abort(400)
    return _binding_response('alert_source', scope_key=scope_key)
