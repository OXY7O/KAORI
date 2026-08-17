from __future__ import annotations

import json
import logging
from dataclasses import replace

from flask import make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.alert_sources.providers.alertmanager.forms import AlertmanagerBindingForm, parse_alertmanager_instance_form
from app.alert_sources.providers.alertmanager.notifications import record_instance_activity
from app.alert_sources.providers.alertmanager.presentation import build_instance_context
from app.alert_sources.providers.alertmanager.registration import issue_registration_proof, verify_registration_proof
from app.alert_sources.providers.alertmanager.service import (
    create_alertmanager_instance,
    get_cluster_by_id,
    test_alertmanager_form_connection,
)
from app.common.http import is_htmx_request
from app.notifications.service import get_navigation_notification_context

logger = logging.getLogger(__name__)


def _htmx_redirect(location: str) -> ResponseReturnValue:
    response = make_response('', 204)
    response.headers['HX-Redirect'] = location
    return response


def new_instance_response() -> ResponseReturnValue:
    initial_cluster_id = request.values.get('cluster_id', '').strip()
    initial_cluster = get_cluster_by_id(initial_cluster_id) if initial_cluster_id else None
    draft_form = None
    registration_proof = None
    operation_feedback = None
    is_htmx = is_htmx_request()

    if request.method == 'POST':
        form = parse_alertmanager_instance_form(request.form)
        if not form.name and initial_cluster is not None:
            form = replace(form, name=f'{initial_cluster.name} Alertmanager', deployment_type='cluster_managed')
        draft_form = form

        submitted_proof = str(request.form.get('connection_test_proof') or '').strip()
        proof_valid, proof_error = verify_registration_proof(
            token=submitted_proof,
            form=form,
            user_id=int(current_user.id),
        )
        if not proof_valid:
            operation_feedback = record_instance_activity(
                user_id=int(current_user.id),
                instance=None,
                event_type='alertmanager_instance_create_rejected',
                status='error',
                title='Connection test required',
                message='Run Test Connection successfully before registering the Alertmanager instance.',
                detail=proof_error,
                metadata={
                    'cluster_id': initial_cluster_id or None,
                    'submitted_name': form.name or 'Draft Alertmanager connection',
                    'registration_stage': 'connection_test_proof',
                },
                queue_feedback=not is_htmx,
            )
        else:
            connection_test = test_alertmanager_form_connection(form)
            if not connection_test.get('connected'):
                failure_detail = (
                    connection_test.get('error')
                    or connection_test.get('reason')
                    or 'Review endpoint, authentication, TLS, and network reachability.'
                )
                operation_feedback = record_instance_activity(
                    user_id=int(current_user.id),
                    instance=None,
                    event_type='alertmanager_instance_create_rejected',
                    status='error',
                    title='Alertmanager instance not created',
                    message='The connection changed or became unreachable before registration completed.',
                    detail=failure_detail,
                    metadata={
                        'cluster_id': initial_cluster_id or None,
                        'failure_code': connection_test.get('failure_code'),
                        'endpoint_host': connection_test.get('endpoint_host'),
                        'request_path': connection_test.get('request_path'),
                        'submitted_name': form.name or 'Draft Alertmanager connection',
                        'registration_stage': 'pre_save_recheck',
                    },
                    queue_feedback=not is_htmx,
                )
            else:
                try:
                    initial_binding = (
                        AlertmanagerBindingForm(
                            scope_type='kubernetes_cluster',
                            scope_key=initial_cluster.id,
                            binding_role='primary',
                            priority=100,
                            enabled=True,
                            selector_label='cluster',
                            selector_value=initial_cluster.name,
                            selector_operator='=',
                        )
                        if initial_cluster is not None
                        else None
                    )
                    instance = create_alertmanager_instance(form=form, initial_binding=initial_binding)
                except ValueError as exc:
                    operation_feedback = record_instance_activity(
                        user_id=int(current_user.id),
                        instance=None,
                        event_type='alertmanager_instance_create_rejected',
                        status='error',
                        title='Alertmanager instance not created',
                        message='KAORI could not create the Alertmanager instance.',
                        detail=str(exc),
                        metadata={
                            'cluster_id': initial_cluster_id or None,
                            'submitted_name': form.name or 'Draft Alertmanager connection',
                            'registration_stage': 'persistence_validation',
                        },
                        queue_feedback=not is_htmx,
                    )
                except Exception as exc:
                    logger.exception('Alertmanager instance creation failed.')
                    operation_feedback = record_instance_activity(
                        user_id=int(current_user.id),
                        instance=None,
                        event_type='alertmanager_instance_create_failed',
                        status='error',
                        title='Alertmanager instance not created',
                        message='KAORI could not save the Alertmanager instance.',
                        detail='Review KAORI logs and database connectivity before retrying.',
                        metadata={
                            'reason': type(exc).__name__,
                            'submitted_name': form.name or 'Draft Alertmanager connection',
                            'registration_stage': 'database_commit',
                        },
                        queue_feedback=not is_htmx,
                    )
                else:
                    record_instance_activity(
                        user_id=int(current_user.id),
                        instance=instance,
                        event_type='alertmanager_instance_created',
                        status='success',
                        title='Alertmanager instance created',
                        message=f'{instance.name} is now registered as an Alertmanager source.',
                        detail='Reachability passed during registration. Run Full Validation, review readiness, then create scope bindings before operational use.',
                        metadata={
                            'initial_cluster_id': initial_cluster_id or None,
                            'connection_response_time_ms': connection_test.get('response_time_ms'),
                            'detected_version': connection_test.get('version'),
                        },
                        queue_feedback=True,
                    )
                    location = url_for('alertmanager.instance_detail', instance_id=instance.id)
                    return _htmx_redirect(location) if is_htmx else redirect(location)

    return render_template(
        'integrations/observability/alert_source/providers/alertmanager/instance_form.html',
        **build_instance_context(),
        initial_cluster=initial_cluster,
        draft_form=draft_form,
        registration_proof=registration_proof,
        operation_feedback=operation_feedback,
        notification_context=(
            get_navigation_notification_context(user_id=int(current_user.id))
            if operation_feedback is not None
            else None
        ),
    )


def test_new_instance_connection_response() -> ResponseReturnValue:
    form = parse_alertmanager_instance_form(request.form)
    result = test_alertmanager_form_connection(form)

    if result.get('connected'):
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=None,
            event_type='alertmanager_connection_test',
            status='success',
            title='Alertmanager connection verified',
            message='KAORI reached the submitted Alertmanager endpoint.',
            detail=(
                f'Status API responded in {result.get("response_time_ms", 0)} ms. '
                'Register the instance, then run full validation from its detail page.'
            ),
            metadata={
                'endpoint_host': result.get('endpoint_host'),
                'version': result.get('version'),
                'response_time_ms': result.get('response_time_ms'),
                'request_path': result.get('request_path'),
                'draft_connection': True,
                'submitted_name': form.name or 'Draft Alertmanager connection',
            },
            queue_feedback=False,
        )
    else:
        feedback = record_instance_activity(
            user_id=int(current_user.id),
            instance=None,
            event_type='alertmanager_connection_test_failed',
            status='error',
            title='Alertmanager connection test failed',
            message='KAORI could not reach the submitted Alertmanager endpoint.',
            detail=result.get('error') or 'Review endpoint, authentication, TLS, and network reachability.',
            metadata={
                'failure_code': result.get('failure_code'),
                'endpoint_host': result.get('endpoint_host'),
                'endpoint_port': result.get('endpoint_port'),
                'request_path': result.get('request_path'),
                'draft_connection': True,
                'submitted_name': form.name or 'Draft Alertmanager connection',
            },
            queue_feedback=False,
        )

    registration_proof = (
        issue_registration_proof(form=form, user_id=int(current_user.id)) if result.get('connected') else ''
    )
    response = make_response(
        render_template(
            'integrations/observability/alert_source/providers/alertmanager/partials/_connection_test_result.html',
            connection_feedback=feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    )
    response.headers['HX-Trigger'] = json.dumps(
        {
            'alertmanager-connection-tested': {
                'connected': bool(result.get('connected')),
                'proof': registration_proof,
            }
        },
        separators=(',', ':'),
    )
    return response
