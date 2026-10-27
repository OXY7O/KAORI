"""HTTP presentation for existing Integration source-binding workspace.

The registered endpoints and permission decorators remain in routes.py.
"""

from flask import abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.common.http import is_htmx_request
from app.common.presentation import present_key_label
from app.integrations.binding_service import SourceBindingSpec, create_source_binding
from app.integrations.coverage import build_binding_workspace
from app.integrations.repository import get_cluster
from app.platform_operations.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)


def _binding_response(integration_type: str, *, scope_key: str) -> ResponseReturnValue:
    submitted = dict(request.form) if request.method == 'POST' else {}
    feedback = None

    if request.method == 'POST':
        source_id = request.form.get('source_id', type=int)
        cluster_id = request.form.get('scope_key', scope_key).strip()
        selector_label = request.form.get('selector_label', '').strip()
        selector_value = request.form.get('selector_value', '').strip()
        selector_operator = request.form.get('selector_operator', '=').strip() or '='
        role = request.form.get('binding_role', 'primary').strip().lower()
        priority = request.form.get('priority', 100, type=int) or 100
        routing_policy = None
        if integration_type == 'metrics_source':
            routing_weight = request.form.get('routing_weight', type=int)
            routing_policy = {
                'query_horizon': request.form.get('query_horizon', 'balanced').strip().lower() or 'balanced',
                'weight': 100 if routing_weight is None else routing_weight,
            }
        source = None
        cluster = None
        binding = None
        try:
            if source_id is None:
                raise ValueError(f'Select an existing {present_key_label(integration_type)} source.')
            cluster = get_cluster(cluster_id)
            if cluster is None:
                raise ValueError('The selected Kubernetes scope no longer exists.')
            created_binding = create_source_binding(
                integration_type,
                integration_instance_id=source_id,
                spec=SourceBindingSpec(
                    asset_type='kubernetes_cluster',
                    asset_key=str(cluster.id),
                    role=role,
                    priority=priority,
                    selector_label=selector_label,
                    selector_value=selector_value,
                    selector_operator=selector_operator,
                    routing_policy=routing_policy,
                ),
                asset=cluster,
            )
            source = created_binding.source
            cluster = created_binding.asset
            binding = created_binding.binding
            if source is None or cluster is None or binding is None:
                raise ValueError('KAORI could not resolve the saved source binding context.')
        except ValueError as exc:
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type=f'{integration_type}_binding_create_rejected',
                status='error',
                title=f'{present_key_label(integration_type)} binding not saved',
                message='KAORI could not create the requested source binding.',
                detail=str(exc),
                action_url=request.path,
                action_label='Review binding',
                action_icon='link-2',
                metadata={
                    'integration_type': integration_type,
                    'scope_type': 'kubernetes_cluster',
                    'scope_key': cluster_id,
                    'source_id': source_id,
                    'selector_label': selector_label or None,
                },
                queue_feedback=not is_htmx_request(),
            )
        except Exception as exc:
            current_app.logger.exception(
                'Unexpected %s binding persistence failure for scope %s and source %s',
                integration_type,
                cluster_id,
                source_id,
            )
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type=f'{integration_type}_binding_create_failed',
                status='error',
                title=f'{present_key_label(integration_type)} binding not saved',
                message='KAORI could not persist the source binding.',
                detail='Review KAORI logs and database connectivity before retrying.',
                action_url=request.path,
                action_label='Review binding',
                action_icon='link-2',
                metadata={
                    'integration_type': integration_type,
                    'scope_key': cluster_id,
                    'source_id': source_id,
                    'reason': type(exc).__name__,
                },
                queue_feedback=not is_htmx_request(),
            )
        else:
            feedback = record_operational_activity(
                user_id=current_user.id,
                event_type=f'{integration_type}_binding_created',
                status='success',
                title=f'{present_key_label(integration_type)} binding saved',
                message=f'{source.name} is associated with {cluster.name} and requires binding validation.',
                detail=f'Binding selector: {selector_label}={selector_value}. Source credentials and runtime remain shared; operational resolution stays blocked until validation succeeds.',
                action_url=(
                    url_for('metrics.instance_detail', instance_id=source.id) + '#scope'
                    if integration_type == 'metrics_source'
                    else url_for('alertmanager.instance_detail', instance_id=source.id) + '#scope'
                ),
                action_label='Review source binding',
                action_icon='route',
                metadata={
                    'integration_type': integration_type,
                    'binding_id': binding.id,
                    'scope_key': cluster.id,
                    'source_id': source.id,
                    'selector_label': selector_label,
                    'selector_value': selector_value,
                },
                queue_feedback=not is_htmx_request(),
            )
            if not is_htmx_request():
                return redirect(
                    url_for(
                        'integrations.metrics_sources'
                        if integration_type == 'metrics_source'
                        else 'integrations.alertmanager'
                    )
                    + '#integration-coverage'
                )

    context = build_binding_workspace(
        integration_type,
        scope_key=scope_key,
        submitted=submitted,
        operation_feedback=feedback,
    )
    if context['cluster'] is None and request.method == 'GET':
        abort(404)
    context['notification_context'] = (
        get_navigation_notification_context(user_id=int(current_user.id)) if feedback is not None else None
    )
    if is_htmx_request():
        return render_template('integrations/bindings/partials/_workspace.html', **context)
    return render_template('integrations/bindings/source.html', **context)

