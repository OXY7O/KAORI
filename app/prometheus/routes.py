from __future__ import annotations

import logging

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.cluster.service import get_cluster_by_id
from app.common.integration_errors import describe_integration_failure
from app.common.presentation import present_user_datetime
from app.integrations.runtime.monitoring import refresh_and_record
from app.integrations.runtime.presentation import runtime_history_view, runtime_state_view
from app.integrations.runtime.repository import paginate_runtime_history
from app.extensions.db import db
from app.integrations.lifecycle import bind_instance, ensure_canonical_instance
from app.models import Cluster, PrometheusInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.prometheus.exceptions import PrometheusError
from app.prometheus.forms import PrometheusConfigForm, PrometheusInstanceForm
from app.prometheus.presentation import build_instance_context, build_runtime_history_context
from app.prometheus.repository import (
    cluster_bindings_for_instance,
    get_instance,
    list_instances,
    primary_cluster_id_for_instance,
    resolve_instance_for_cluster,
)
from app.prometheus.runtime_adapter import runtime_adapter
from app.prometheus.service import (
    PrometheusService,
    remove_prometheus_instance,
    save_prometheus_instance,
)
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)


def _runtime_view(cluster, state):
    """Build a self-contained, cluster-bound Prometheus runtime view model."""
    return runtime_state_view(
        state,
        actions={
            'refresh_url': url_for('prometheus.validate_integration', cluster_id=cluster.id),
            'configuration_url': url_for('prometheus.configuration', cluster_id=cluster.id),
        },
        binding={
            'type': 'kubernetes_cluster',
            'id': str(cluster.id),
            'name': cluster.name,
            'label': f'Kubernetes cluster {cluster.name}',
        },
    )

prometheus_bp = Blueprint(
    'prometheus',
    __name__,
    url_prefix='/integrations/prometheus',
)


def _get_cluster_or_404(
    cluster_id: str,
) -> Cluster:
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(
            404,
        )

    return cluster


def _runtime_source(cluster):
    return resolve_instance_for_cluster(cluster.id)


def _instance_or_404(instance_id: int) -> PrometheusInstance:
    instance = get_instance(instance_id)
    if instance is None:
        abort(404)
    return instance


def _optional_endpoint_url(endpoint: str, **values) -> str | None:
    """Build a lifecycle URL only when the endpoint is registered.

    Contextual workspaces must remain renderable even when a partial deployment
    has not loaded an optional lifecycle route yet. The missing endpoint is
    logged as a deployment inconsistency instead of raising BuildError in Jinja.
    """
    if endpoint not in current_app.view_functions:
        logger.error('Prometheus endpoint %s is not registered.', endpoint)
        return None
    return url_for(endpoint, **values)


def _instance_detail_context(
    instance: PrometheusInstance,
    *,
    page: int = 1,
    per_page: int = 5,
) -> dict:
    """Build the complete Prometheus manage-workspace context.

    All full-page and HTMX partial responses use the same context builder so
    Configuration, Validation, Runtime, Scope, and lifecycle controls cannot
    drift or render with missing route dependencies.
    """
    context = build_instance_context(instance, page=page, per_page=per_page)
    context['delete_instance_url'] = _optional_endpoint_url(
        'prometheus.delete_instance',
        instance_id=instance.id,
    )
    return context


def _cluster_for_instance_or_404(instance: PrometheusInstance) -> Cluster:
    cluster_id = primary_cluster_id_for_instance(instance)
    if cluster_id is None:
        abort(409, description='Prometheus instance has no enabled Kubernetes cluster binding.')
    return _get_cluster_or_404(cluster_id)


@prometheus_bp.route('/instances/new', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def new_instance() -> ResponseReturnValue:
    cluster_id = request.values.get('cluster_id', '').strip()
    initial_cluster = get_cluster_by_id(cluster_id) if cluster_id else None
    form = PrometheusInstanceForm()
    if request.method == 'GET':
        form.enabled.data = True
        form.verify_ssl.data = True
    if form.validate_on_submit():
        try:
            instance = save_prometheus_instance(form, initial_cluster=initial_cluster)
        except Exception as exc:
            logger.exception('Prometheus instance creation failed.')
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_instance_create_failed',
                status='error',
                title='Prometheus instance not created',
                message='KAORI could not save the Prometheus instance.',
                detail=str(exc),
                action_url=url_for('prometheus.new_instance', cluster_id=cluster_id or None),
                action_label='Review Prometheus form',
                action_icon='activity',
                metadata={'cluster_id': cluster_id or None, 'reason': type(exc).__name__},
                queue_feedback=True,
            )
        else:
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_instance_created',
                status='success',
                title='Prometheus instance created',
                message=f'{instance.name} is now registered.',
                detail='Test the connection and run full validation before Analytics uses this source.',
                action_url=url_for('prometheus.instance_detail', instance_id=instance.id),
                action_label='Open Prometheus runtime',
                action_icon='activity',
                metadata={'instance_id': instance.id, 'cluster_id': cluster_id or None},
                queue_feedback=True,
            )
            return redirect(url_for('prometheus.instance_detail', instance_id=instance.id))
    return render_template('prometheus/instance_form.html', form=form, instance=None, initial_cluster=initial_cluster)


@prometheus_bp.route('/instances/<int:instance_id>/edit', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def edit_instance(instance_id: int) -> ResponseReturnValue:
    """Compatibility route for bookmarks created before inline management.

    Prometheus configuration is now edited directly in the manage workspace,
    matching Alertmanager. GET requests therefore redirect to the Configuration
    tab. POST remains accepted for stale clients and uses the same save contract.
    """
    instance = _instance_or_404(instance_id)
    if request.method == 'GET':
        return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration')

    form = PrometheusInstanceForm(obj=instance)
    form.existing_instance = instance
    if form.validate_on_submit():
        try:
            instance = save_prometheus_instance(form, instance=instance)
        except Exception as exc:
            logger.exception('Prometheus instance update failed for %s.', instance_id)
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_instance_update_failed',
                status='error',
                title='Prometheus instance not updated',
                message=f'KAORI could not update {instance.name}.',
                detail=str(exc),
                action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
                action_label='Review Prometheus configuration',
                action_icon='settings-2',
                metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
                queue_feedback=True,
            )
        else:
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_instance_updated',
                status='success',
                title='Prometheus instance updated',
                message=f'{instance.name} connection settings were saved.',
                detail='Readiness returned to Validation Required.',
                action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
                action_label='Review Prometheus validation',
                action_icon='scan-search',
                metadata={'instance_id': instance.id},
                queue_feedback=True,
            )
    else:
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_instance_update_rejected',
            status='error',
            title='Prometheus instance not updated',
            message=f'KAORI could not update {instance.name}.',
            detail='Review the inline Configuration tab and correct the highlighted fields.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
            action_label='Review Prometheus configuration',
            action_icon='settings-2',
            metadata={'instance_id': instance.id, 'fields': sorted(form.errors)},
            queue_feedback=True,
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration')


@prometheus_bp.get('/instances')
@permission_required('settings.manage_integrations')
def instances() -> ResponseReturnValue:
    rows = []
    for instance in list_instances():
        bindings = cluster_bindings_for_instance(instance)
        rows.append({
            'instance': instance,
            'bindings': bindings,
            'binding_count': len(bindings),
            'primary_cluster_id': bindings[0].asset_key if bindings else None,
            'detail_url': url_for('prometheus.instance_detail', instance_id=instance.id),
            'status_label': (instance.readiness_status or 'validation_required').replace('_', ' ').title(),
            'last_checked_at_display': present_user_datetime(instance.last_checked_at, empty='Not checked yet'),
        })
    clusters = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    return render_template('prometheus/instances.html', rows=rows, clusters=clusters)


@prometheus_bp.route('/instances/<int:instance_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def instance_detail(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    form = PrometheusInstanceForm(obj=instance)
    form.existing_instance = instance

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                instance = save_prometheus_instance(form, instance=instance)
            except Exception as exc:
                logger.exception('Prometheus instance update failed for %s.', instance_id)
                record_operational_activity(
                    user_id=current_user.id,
                    event_type='prometheus_instance_update_failed',
                    status='error',
                    title='Prometheus instance not updated',
                    message=f'KAORI could not update {instance.name}.',
                    detail=str(exc),
                    action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
                    action_label='Review Prometheus configuration',
                    action_icon='settings-2',
                    metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
                    queue_feedback=True,
                )
            else:
                record_operational_activity(
                    user_id=current_user.id,
                    event_type='prometheus_instance_updated',
                    status='success',
                    title='Prometheus instance updated',
                    message=f'{instance.name} connection settings were saved.',
                    detail='Readiness returned to Validation Required until Full Validation rebuilds the technical evidence.',
                    action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
                    action_label='Review Prometheus validation',
                    action_icon='scan-search',
                    metadata={'instance_id': instance.id},
                    queue_feedback=True,
                )
            return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration')

        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_instance_update_rejected',
            status='error',
            title='Prometheus instance not updated',
            message=f'KAORI could not update {instance.name}.',
            detail='Review the highlighted configuration fields before saving again.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#configuration',
            action_label='Review Prometheus configuration',
            action_icon='settings-2',
            metadata={'instance_id': instance.id, 'fields': sorted(form.errors)},
            queue_feedback=True,
        )

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    context = _instance_detail_context(instance, page=page, per_page=per_page)
    context['form'] = form
    return render_template('prometheus/instance_detail.html', **context)


@prometheus_bp.post('/instances/<int:instance_id>/bindings')
@permission_required('settings.manage_integrations')
def add_instance_binding(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    cluster_id = request.form.get('cluster_id', '').strip()
    cluster = get_cluster_by_id(cluster_id) if cluster_id else None
    role = (request.form.get('binding_role') or 'primary').strip().lower()
    priority = request.form.get('priority', 100, type=int) or 100
    is_htmx = request.headers.get('HX-Request') == 'true'

    error = None
    if cluster is None:
        error = 'Select an available managed cluster.'
    elif role not in {'primary', 'secondary', 'fallback'}:
        error = 'Select a supported source role.'
    elif priority < 1 or priority > 1000:
        error = 'Priority must be between 1 and 1000.'
    elif instance.integration_instance_id is not None and IntegrationBinding.query.filter_by(
        integration_instance_id=instance.integration_instance_id,
        asset_type='kubernetes_cluster',
        asset_key=cluster.id,
    ).first() is not None:
        error = 'This Prometheus instance is already bound to the selected managed cluster.'
    elif role == 'primary':
        conflicting_primary = (
            IntegrationBinding.query
            .join(
                IntegrationInstance,
                IntegrationBinding.integration_instance_id == IntegrationInstance.id,
            )
            .filter(
                IntegrationInstance.provider_type == 'prometheus',
                IntegrationBinding.asset_type == 'kubernetes_cluster',
                IntegrationBinding.asset_key == cluster.id,
                IntegrationBinding.binding_role == 'primary',
                IntegrationBinding.enabled.is_(True),
            )
            .first()
        )
        if conflicting_primary is not None:
            error = 'The selected managed cluster already has an enabled primary Prometheus source.'

    if error is None:
        try:
            canonical = ensure_canonical_instance(instance, provider_type='prometheus')
            binding = bind_instance(
                canonical,
                asset_type='kubernetes_cluster',
                asset_key=cluster.id,
                role=role,
                priority=priority,
                capability_scope=[
                    'metrics', 'capacity', 'utilization', 'storage', 'workload',
                    'forecast', 'top_consumers', 'alert_metrics',
                ],
            )
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.exception('Prometheus binding creation failed for instance %s.', instance_id)
            error = 'KAORI could not save the scope binding. Review database connectivity and retry.'
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_binding_create_failed',
                status='error',
                title='Prometheus binding not saved',
                message=f"KAORI could not bind {instance.name} to {cluster.name if cluster else 'the selected scope'}.",
                detail=error,
                action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
                action_label='Review Prometheus scope',
                action_icon='waypoints',
                metadata={'instance_id': instance.id, 'cluster_id': cluster.id if cluster else cluster_id or None, 'reason': type(exc).__name__},
                queue_feedback=not is_htmx,
            )
        else:
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_binding_created',
                status='success',
                title='Prometheus binding created',
                message=f'{instance.name} is now available to {cluster.name}.',
                detail=f'{role.title()} source with priority {priority}.',
                action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
                action_label='Review Prometheus scope',
                action_icon='waypoints',
                metadata={'instance_id': instance.id, 'binding_id': binding.id, 'cluster_id': cluster.id},
                queue_feedback=not is_htmx,
            )
    else:
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_create_rejected',
            status='error',
            title='Prometheus binding not saved',
            message=f"KAORI could not bind {instance.name} to {cluster.name if cluster else 'the selected scope'}.",
            detail=error,
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={'instance_id': instance.id, 'cluster_id': cluster.id if cluster else cluster_id or None, 'binding_role': role, 'priority': priority},
            queue_feedback=not is_htmx,
        )

    if is_htmx:
        context = _instance_detail_context(instance)
        return render_template('prometheus/partials/_detail_scope.html', **context, binding_error=error)
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope')


@prometheus_bp.post('/instances/<int:instance_id>/bindings/<int:binding_id>/delete')
@permission_required('settings.manage_integrations')
def delete_instance_binding(instance_id: int, binding_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    binding = IntegrationBinding.query.filter_by(
        id=binding_id,
        integration_instance_id=instance.integration_instance_id,
    ).first()
    if binding is None:
        abort(404)
    binding_metadata = {
        'instance_id': instance.id,
        'instance_name': instance.name,
        'binding_id': binding.id,
        'asset_type': binding.asset_type,
        'asset_key': binding.asset_key,
        'binding_role': binding.binding_role,
    }
    try:
        db.session.delete(binding)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception('Prometheus binding deletion failed for binding %s.', binding_id)
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_delete_failed',
            status='error',
            title='Prometheus binding not removed',
            message=f'KAORI could not remove the selected binding from {instance.name}.',
            detail='Review KAORI logs and database connectivity before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={**binding_metadata, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    else:
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_binding_deleted',
            status='success',
            title='Prometheus binding removed',
            message=f'{instance.name} is no longer mapped to the selected managed cluster.',
            detail=f'{binding.asset_type}:{binding.asset_key} was removed.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata=binding_metadata,
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return render_template('prometheus/partials/_detail_scope.html', **_instance_detail_context(instance))
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#scope')


@prometheus_bp.post(
    '/instances/<int:instance_id>/delete',
    endpoint='delete_instance',
)
@permission_required('settings.manage_integrations')
def delete_instance(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    instance_name = instance.name
    try:
        remove_prometheus_instance(instance)
    except ValueError as exc:
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_instance_delete_rejected',
            status='error',
            title='Prometheus instance not deleted',
            message=f'{instance_name} still has scope bindings.',
            detail=str(exc),
            action_url=url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={'instance_id': instance_id, 'instance_name': instance_name},
            queue_feedback=True,
        )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope')
    except Exception as exc:
        logger.exception('Prometheus instance deletion failed for %s.', instance_id)
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_instance_delete_failed',
            status='error',
            title='Prometheus instance not deleted',
            message=f'KAORI could not delete {instance_name}.',
            detail='Review KAORI logs and database connectivity before retrying the deletion.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope',
            action_label='Review Prometheus scope',
            action_icon='waypoints',
            metadata={'instance_id': instance_id, 'instance_name': instance_name, 'reason': type(exc).__name__},
            queue_feedback=True,
        )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance_id) + '#scope')

    record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_instance_deleted',
        status='success',
        title='Prometheus instance deleted',
        message=f'{instance_name} was removed from the integration registry.',
        detail='Historical runtime observations and Activity Audit records remain available.',
        action_url=url_for('integrations.prometheus'),
        action_label='Open Prometheus integrations',
        action_icon='activity',
        metadata={'instance_id': instance_id, 'instance_name': instance_name},
        queue_feedback=True,
    )
    return redirect(url_for('integrations.prometheus'))


@prometheus_bp.post('/instances/<int:instance_id>/test')
@permission_required('settings.manage_integrations')
def instance_test(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    try:
        result = PrometheusService(instance).test_connection()
        ensure_canonical_instance(instance, provider_type='prometheus')
        db.session.commit()
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test',
            status='success',
            title='Prometheus connection verified',
            message=f'KAORI connected to {instance.name}.',
            detail=f'{(result.get("endpoint_product") or "endpoint").title()} {result.get("endpoint_version", "unknown")} responded successfully.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id),
            action_label='View Prometheus instance',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'endpoint': instance.endpoint},
            queue_feedback=True,
        )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation')
    except PrometheusError as exc:
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test',
            status='error',
            title='Prometheus connection failed',
            message=f'KAORI could not connect to {instance.name}.',
            detail=str(exc),
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id),
            action_label='Review Prometheus instance',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'instance_name': instance.name},
            queue_feedback=True,
        )
        return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation')


@prometheus_bp.post('/instances/<int:instance_id>/validate')
@permission_required('settings.manage_integrations')
def instance_validate(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        result, _state, _observation = refresh_and_record(
            runtime_adapter,
            instance,
            trigger_type='manual',
        )
        ensure_canonical_instance(instance, provider_type='prometheus')
        db.session.commit()
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_compatibility_validation',
            status='success' if result.get('success') else 'warning',
            title='Prometheus validation completed',
            message=f'Full Validation completed for {instance.name}.',
            detail=result.get('message') or 'Compatibility, capabilities, query contracts, retention, and module readiness were evaluated.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'readiness_status': result.get('readiness_status')},
            queue_feedback=not is_htmx,
        )
    except PrometheusError as exc:
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_compatibility_validation',
            status='error',
            title='Prometheus validation failed',
            message=f'Full Validation failed for {instance.name}.',
            detail=str(exc),
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'instance_name': instance.name},
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        db.session.rollback()
        logger.exception('Prometheus full validation failed for %s.', instance_id)
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_compatibility_validation',
            status='error',
            title='Prometheus validation failed',
            message=f'KAORI could not complete Full Validation for {instance.name}.',
            detail='Review endpoint access, query permissions, runtime logs, and observation storage before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation',
            action_label='Review Prometheus validation',
            action_icon='scan-search',
            metadata={'instance_id': instance.id, 'instance_name': instance.name, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        return render_template(
            'prometheus/partials/_detail_validation_content.html',
            **_instance_detail_context(instance),
        )
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#validation')


@prometheus_bp.post('/instances/<int:instance_id>/runtime/refresh')
@permission_required('settings.manage_integrations')
def refresh_runtime(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    try:
        result, state, _observation = refresh_and_record(
            runtime_adapter,
            instance,
            trigger_type='manual',
        )
        ensure_canonical_instance(instance, provider_type='prometheus')
        db.session.commit()
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_runtime_refreshed',
            status='success' if state.health.status == 'healthy' else ('warning' if state.health.status == 'degraded' else 'error'),
            title='Prometheus runtime refreshed',
            message=f'{instance.name} runtime health is {state.health.status}.',
            detail=result.get('message') or state.message,
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#runtime',
            action_label='Review Prometheus runtime',
            action_icon='activity',
            metadata={
                'instance_id': instance.id,
                'health_status': state.health.status,
                'health_score': state.health.score,
                'readiness_status': state.readiness,
                'latency_ms': state.latency_ms,
            },
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('Prometheus runtime refresh failed for %s.', instance_id)
        state = runtime_adapter.get_state(instance)
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_runtime_refresh_failed',
            status='error',
            title='Prometheus runtime refresh failed',
            message=f'KAORI could not refresh runtime health for {instance.name}.',
            detail='Review endpoint reachability, authentication, TLS, query access, and runtime observation storage before retrying.',
            action_url=url_for('prometheus.instance_detail', instance_id=instance.id) + '#runtime',
            action_label='Review Prometheus runtime',
            action_icon='activity',
            metadata={'instance_id': instance.id, 'reason': type(exc).__name__},
            queue_feedback=not is_htmx,
        )
    if is_htmx:
        context = _instance_detail_context(instance)
        return render_template('prometheus/partials/_runtime_refresh_response.html', **context)
    return redirect(url_for('prometheus.instance_detail', instance_id=instance.id) + '#runtime')


@prometheus_bp.get('/instances/<int:instance_id>/runtime/history')
@permission_required('settings.manage_integrations')
def instance_runtime_history(instance_id: int) -> ResponseReturnValue:
    instance = _instance_or_404(instance_id)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    rows, pagination = paginate_runtime_history(
        'prometheus', str(instance.id), page=page, per_page=per_page,
    )
    return render_template(
        'prometheus/partials/_runtime_history.html',
        instance=instance,
        runtime_history=runtime_history_view(rows, pagination=pagination),
    )



@prometheus_bp.route(
    '/cluster/<string:cluster_id>',
    methods=[
        'GET',
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def configuration(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(
        cluster_id,
    )

    config = _runtime_source(cluster)

    if config is None:
        return redirect(url_for('prometheus.instances'))

    form = PrometheusConfigForm()

    if form.validate_on_submit():
        try:
            was_configured = bool(config and config.endpoint)
            saved_config = PrometheusService.save_config(
                cluster,
                form,
            )

            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_configuration_update' if was_configured else 'prometheus_configuration_create',
                status='success',
                title='Prometheus configuration updated' if was_configured else 'Prometheus configured',
                message=f'Prometheus settings for {cluster.name} were saved successfully.',
                detail='KAORI will use the saved endpoint, authentication method, timeout, and TLS verification settings for metric queries.',
                action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
                action_label='View Prometheus settings',
                action_icon='activity',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'endpoint': saved_config.endpoint,
                    'auth_type': saved_config.auth_type,
                    'timeout_seconds': saved_config.timeout,
                    'verify_ssl': saved_config.verify_ssl,
                    'version_detection_mode': saved_config.version_detection_mode,
                    'source_prometheus_major': saved_config.source_prometheus_major,
                },
                queue_feedback=True,
            )

            return redirect(
                url_for(
                    'prometheus.configuration',
                    cluster_id=cluster.id,
                )
            )

        except PrometheusError as exc:
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_configuration_update' if config else 'prometheus_configuration_create',
                status='error',
                title='Prometheus configuration not saved',
                message=str(exc),
                detail='Review the endpoint, authentication fields, timeout, and TLS configuration before saving again.',
                action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
                action_label='Review Prometheus settings',
                action_icon='activity',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'reason': type(exc).__name__,
                },
                queue_feedback=True,
            )
        except Exception as exc:
            logger.exception(
                'Prometheus configuration save failed for cluster %s.',
                cluster.id,
            )
            record_operational_activity(
                user_id=current_user.id,
                event_type='prometheus_configuration_update' if config else 'prometheus_configuration_create',
                status='error',
                title='Prometheus configuration not saved',
                message=f'KAORI could not save Prometheus settings for {cluster.name}.',
                detail='Review application logs and database connectivity before retrying the configuration save.',
                action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
                action_label='Review Prometheus settings',
                action_icon='activity',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'reason': type(exc).__name__,
                },
                queue_feedback=True,
            )

    elif request.method == 'POST' and form.errors:
        record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_configuration_update' if config else 'prometheus_configuration_create',
            status='warning',
            title='Prometheus configuration needs attention',
            message='The submitted Prometheus configuration contains validation errors.',
            detail='Correct the highlighted fields before saving the integration.',
            action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
            action_label='Review Prometheus settings',
            action_icon='activity',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'validation_fields': sorted(form.errors.keys()),
            },
            queue_feedback=True,
        )

    elif config:
        form.endpoint.data = config.endpoint
        form.version_detection_mode.data = config.version_detection_mode or 'automatic'
        form.source_prometheus_major.data = config.source_prometheus_major or ''
        form.auth_type.data = config.auth_type
        form.username.data = config.username
        form.password.data = config.password
        form.bearer_token.data = config.bearer_token
        form.timeout.data = config.timeout
        form.verify_ssl.data = config.verify_ssl

    runtime_state = _runtime_view(cluster, runtime_adapter.get_state(config)) if config else None
    history_rows, history_pagination = (
        paginate_runtime_history('prometheus', str(config.id), page=1, per_page=5)
        if config else ([], {'page': 1, 'per_page': 5, 'total_items': 0, 'total_pages': 1, 'start_item': 0, 'end_item': 0, 'has_prev': False, 'has_next': False, 'prev_page': 0, 'next_page': 2, 'allowed_per_page': (5,10,25,50)})
    )
    return render_template(
        'prometheus/config.html',
        cluster=cluster,
        config=config,
        form=form,
        runtime_state=runtime_state,
        runtime_history=runtime_history_view(history_rows, pagination=history_pagination),
        config_last_validated_at_display=present_user_datetime(
            config.last_validated_at if config else None,
            empty='Not validated yet',
        ),
    )


@prometheus_bp.route(
    '/cluster/<string:cluster_id>/test',
    methods=[
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def test_connection(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(
        cluster_id,
    )

    try:
        service = PrometheusService(
            cluster,
        )

        result = service.test_connection()
        response_time = result.get('response_time', 0)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test',
            status='success',
            title='Prometheus connection verified',
            message=f'KAORI connected to Prometheus for {cluster.name}.',
            detail=f'{(result.get("endpoint_product") or "endpoint").title()} {result.get("endpoint_version", "unknown")} responded in {response_time}s.',
            action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
            action_label='View Prometheus settings',
            action_icon='activity',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'endpoint_product': result.get('endpoint_product'),
                'endpoint_version': result.get('endpoint_version', 'unknown'),
                'source_prometheus_major': result.get('source_prometheus_major'),
                'response_time_seconds': response_time,
            },
        )

        if request.headers.get('HX-Request') == 'true':
            return render_template(
                'prometheus/partials/_validation_response.html',
                **feedback,
                config=resolve_instance_for_cluster(cluster.id),
                config_last_validated_at_display=present_user_datetime(
                    resolve_instance_for_cluster(cluster.id).last_validated_at if resolve_instance_for_cluster(cluster.id) else None,
                    empty='Not validated yet',
                ),
                runtime_state=(
                    _runtime_view(cluster, runtime_adapter.get_state(_runtime_source(cluster)))
                    if resolve_instance_for_cluster(cluster.id) else None
                ),
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify(result)

    except PrometheusError as exc:
        config = _runtime_source(cluster)
        failure = describe_integration_failure(
            exc,
            service_name='Prometheus',
            endpoint=config.endpoint if config is not None else None,
            request_path='/api/v1/query',
            timeout_seconds=(min(max(int(config.timeout or 5), 1), 5) if config is not None else None),
        )
        logger.warning(
            'Prometheus connection test failed for cluster %s: %s',
            cluster.id,
            exc,
            exc_info=True,
        )
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test',
            status='error',
            title='Prometheus connection failed',
            message=f'KAORI could not connect to Prometheus for {cluster.name}.',
            detail=failure['detail'],
            action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
            action_label='Review Prometheus settings',
            action_icon='activity',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'reason': failure['reason'],
                'failure_code': failure['code'],
                'endpoint_host': failure['endpoint_host'],
                'endpoint_port': failure['endpoint_port'],
                'request_path': failure['request_path'],
            },
        )

        if request.headers.get('HX-Request') == 'true':
            return render_template(
                'prometheus/partials/_validation_response.html',
                **feedback,
                config=resolve_instance_for_cluster(cluster.id),
                config_last_validated_at_display=present_user_datetime(
                    resolve_instance_for_cluster(cluster.id).last_validated_at if resolve_instance_for_cluster(cluster.id) else None,
                    empty='Not validated yet',
                ),
                runtime_state=(
                    _runtime_view(cluster, runtime_adapter.get_state(_runtime_source(cluster)))
                    if resolve_instance_for_cluster(cluster.id) else None
                ),
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify(
            {
                'success': False,
                'error': failure['detail'],
                'reason': failure['reason'],
                'failure_code': failure['code'],
            }
        ), 400
    except Exception as exc:
        logger.exception(
            'Prometheus connection test failed unexpectedly for cluster %s.',
            cluster.id,
        )
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_connection_test',
            status='error',
            title='Prometheus connection test failed',
            message=f'The Prometheus test for {cluster.name} could not complete.',
            detail='Review application logs, endpoint reachability, authentication, and TLS settings before retrying.',
            action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
            action_label='Review Prometheus settings',
            action_icon='activity',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'reason': type(exc).__name__,
            },
        )

        if request.headers.get('HX-Request') == 'true':
            return render_template(
                'prometheus/partials/_validation_response.html',
                **feedback,
                config=resolve_instance_for_cluster(cluster.id),
                config_last_validated_at_display=present_user_datetime(
                    resolve_instance_for_cluster(cluster.id).last_validated_at if resolve_instance_for_cluster(cluster.id) else None,
                    empty='Not validated yet',
                ),
                runtime_state=(
                    _runtime_view(cluster, runtime_adapter.get_state(_runtime_source(cluster)))
                    if resolve_instance_for_cluster(cluster.id) else None
                ),
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify(
            {
                'success': False,
                'error': 'Prometheus connection test could not complete.',
            }
        ), 500

@prometheus_bp.post('/cluster/<string:cluster_id>/validate')
@permission_required('settings.manage_integrations')
def validate_integration(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(cluster_id)

    try:
        result, runtime_state_obj, _observation = refresh_and_record(runtime_adapter, _runtime_source(cluster), trigger_type='manual')
        response_time = result.get('response_time', 0)
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_compatibility_validation',
            status='success' if result.get('success') else 'warning',
            title='Prometheus validation completed',
            message=f'Compatibility validation completed for {cluster.name}.',
            detail=(
                f"Profile {result.get('compatibility_profile') or 'not matched'}; "
                f"readiness {result.get('readiness_status', 'unknown')}; "
                f"completed in {response_time}s."
            ),
            action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
            action_label='View Prometheus settings',
            action_icon='activity',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'endpoint_product': result.get('endpoint_product'),
                'endpoint_version': result.get('endpoint_version', 'unknown'),
                'source_prometheus_major': result.get('source_prometheus_major'),
                'compatibility_profile': result.get('compatibility_profile'),
                'readiness_status': result.get('readiness_status'),
                'query_validation_status': result.get('query_validation_status'),
                'response_time_seconds': response_time,
            },
        )

        if request.headers.get('HX-Request') == 'true':
            return render_template(
                'prometheus/partials/_validation_response.html',
                **feedback,
                config=resolve_instance_for_cluster(cluster.id),
                config_last_validated_at_display=present_user_datetime(
                    resolve_instance_for_cluster(cluster.id).last_validated_at if resolve_instance_for_cluster(cluster.id) else None,
                    empty='Not validated yet',
                ),
                runtime_state=(
                    _runtime_view(cluster, runtime_adapter.get_state(_runtime_source(cluster)))
                    if resolve_instance_for_cluster(cluster.id) else None
                ),
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify(result)

    except PrometheusError as exc:
        config = _runtime_source(cluster)
        failure = describe_integration_failure(
            exc,
            service_name='Prometheus',
            endpoint=config.endpoint if config is not None else None,
            request_path='/api/v1/series',
            timeout_seconds=(
                min(max(int(config.timeout or 5), 1), 5)
                if config is not None
                else None
            ),
        )
        logger.warning(
            'Prometheus compatibility validation failed for cluster %s: %s',
            cluster.id,
            exc,
            exc_info=True,
        )
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='prometheus_compatibility_validation',
            status='error',
            title='Prometheus validation failed',
            message=f'KAORI could not complete Prometheus validation for {cluster.name}.',
            detail=failure['detail'],
            action_url=url_for('prometheus.configuration', cluster_id=cluster.id),
            action_label='Review Prometheus settings',
            action_icon='activity',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'reason': failure['reason'],
                'failure_code': failure['code'],
                'endpoint_host': failure['endpoint_host'],
                'endpoint_port': failure['endpoint_port'],
                'request_path': failure['request_path'],
            },
        )

        if request.headers.get('HX-Request') == 'true':
            return render_template(
                'prometheus/partials/_validation_response.html',
                **feedback,
                config=resolve_instance_for_cluster(cluster.id),
                config_last_validated_at_display=present_user_datetime(
                    resolve_instance_for_cluster(cluster.id).last_validated_at if resolve_instance_for_cluster(cluster.id) else None,
                    empty='Not validated yet',
                ),
                runtime_state=(
                    _runtime_view(cluster, runtime_adapter.get_state(_runtime_source(cluster)))
                    if resolve_instance_for_cluster(cluster.id) else None
                ),
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify({'success': False, 'error': failure['detail']}), 400


@prometheus_bp.get('/cluster/<string:cluster_id>/runtime/history')
@permission_required('settings.manage_integrations')
def runtime_history(cluster_id: str) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(cluster_id)
    config = _runtime_source(cluster)
    if config is None:
        abort(404)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 5, type=int)
    rows, pagination = paginate_runtime_history('prometheus', str(config.id), page=page, per_page=per_page)
    return render_template(
        'prometheus/partials/_runtime_history.html',
        cluster=cluster, config=config,
        runtime_history=runtime_history_view(rows, pagination=pagination),
    )
