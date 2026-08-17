from __future__ import annotations

import json
import logging

from flask import abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.cluster.service import get_cluster_by_id
from app.common.http import is_htmx_request
from app.integrations.metrics.exceptions import MetricsSourceError
from app.integrations.metrics.providers import MetricsProviderDefinition, provider_definition
from app.notifications.service import get_navigation_notification_context, record_operational_activity
from app.metrics.forms import MetricsSourceForm
from app.metrics.registration import issue_registration_proof, verify_registration_proof
from app.metrics.service import save_metrics_source, test_metrics_source_connection

logger = logging.getLogger(__name__)


def new_instance_response(*, provider_key: str) -> ResponseReturnValue:
    provider = _provider_or_404(provider_key)
    cluster_id = request.values.get('cluster_id', '').strip()
    initial_cluster = get_cluster_by_id(cluster_id) if cluster_id else None
    form = MetricsSourceForm()
    _apply_provider_contract(form, provider)
    if request.method == 'GET':
        form.enabled.data = True
        form.verify_ssl.data = True

    operation_feedback = None
    if request.method == 'POST':
        response, operation_feedback = _register_submitted_source(
            form=form,
            cluster_id=cluster_id,
            provider=provider,
            initial_cluster=initial_cluster,
        )
        if response is not None:
            return response

    return render_template(
        'metrics/instance_form.html',
        form=form,
        instance=None,
        provider=provider,
        initial_cluster=initial_cluster,
        registration_proof=None,
        operation_feedback=operation_feedback,
        notification_context=(
            get_navigation_notification_context(user_id=int(current_user.id))
            if operation_feedback is not None
            else None
        ),
    )


def _register_submitted_source(
    *,
    form: MetricsSourceForm,
    cluster_id: str,
    provider: MetricsProviderDefinition,
    initial_cluster,
) -> tuple[ResponseReturnValue | None, object | None]:
    is_htmx = is_htmx_request()
    _apply_provider_contract(form, provider)
    action_url = _registration_url(provider.key, cluster_id=cluster_id)
    draft_name = (form.name.data or '').strip() or f'Draft {provider.label} connection'
    if not form.validate_on_submit():
        return None, _invalid_form_feedback(
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            provider=provider,
            fields=sorted(form.errors),
            queue_feedback=not is_htmx,
        )

    submitted_proof = str(request.form.get('connection_test_proof') or '').strip()
    proof_valid, proof_error = verify_registration_proof(
        token=submitted_proof,
        form=form,
        user_id=int(current_user.id),
    )
    if not proof_valid:
        return None, record_operational_activity(
            user_id=current_user.id,
            event_type='metrics_source_create_rejected',
            status='error',
            title='Connection test required',
            message=f'Run Test Connection successfully before registering the {provider.label} connection.',
            detail=proof_error,
            action_url=action_url,
            action_label=f'Review {provider.label} form',
            action_icon=provider.icon,
            metadata={
                'cluster_id': cluster_id or None,
                'submitted_name': draft_name,
                'metrics_provider_key': provider.key,
                'metrics_adapter_key': provider.adapter_key,
                'metrics_query_language': provider.query_language,
                'registration_stage': 'connection_test_proof',
            },
            queue_feedback=not is_htmx,
        )

    connection_test = test_metrics_source_connection(form.to_configuration_input())
    if not connection_test.get('connected'):
        return None, _pre_save_connection_failure(
            connection_test=connection_test,
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            provider=provider,
            queue_feedback=not is_htmx,
        )

    try:
        instance = save_metrics_source(form.to_configuration_input(), initial_cluster=initial_cluster)
    except MetricsSourceError as exc:
        return None, _persistence_failure(
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            provider=provider,
            detail=str(exc),
            stage='persistence_validation',
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('%s metrics-source creation failed.', provider.label)
        return None, _persistence_failure(
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            provider=provider,
            detail='Review KAORI logs and database connectivity before retrying.',
            stage='database_commit',
            reason=type(exc).__name__,
            queue_feedback=not is_htmx,
        )

    record_operational_activity(
        user_id=current_user.id,
        event_type='metrics_source_created',
        status='success',
        title=f'{provider.label} connection registered',
        message=f'{instance.name} is now registered as a reusable metrics source.',
        detail=(
            'Reachability and compatibility passed during registration. Run Full Validation, '
            'review readiness, then create consumer bindings before operational use.'
        ),
        action_url=url_for('metrics.instance_detail', instance_id=instance.id),
        action_label='Open Metrics Source',
        action_icon=provider.icon,
        metadata={
            'instance_id': instance.id,
            'cluster_id': cluster_id or None,
            'metrics_provider_key': provider.key,
            'metrics_adapter_key': provider.adapter_key,
            'metrics_query_language': provider.query_language,
            'connection_response_time_ms': connection_test.get('response_time_ms'),
            'detected_version': connection_test.get('version'),
            'endpoint_product': connection_test.get('endpoint_product'),
        },
        queue_feedback=True,
    )
    location = url_for('metrics.instance_detail', instance_id=instance.id)
    return (_htmx_redirect(location) if is_htmx else redirect(location)), None


def test_new_instance_connection_response(*, provider_key: str) -> ResponseReturnValue:
    provider = _provider_or_404(provider_key)
    form = MetricsSourceForm()
    _apply_provider_contract(form, provider)
    cluster_id = request.form.get('cluster_id', '').strip()
    action_url = _registration_url(provider.key, cluster_id=cluster_id)

    if not form.validate_on_submit():
        result = {'connected': False}
        feedback = _connection_test_invalid_feedback(
            form=form,
            action_url=action_url,
            cluster_id=cluster_id,
            provider=provider,
        )
    else:
        result = test_metrics_source_connection(form.to_configuration_input())
        feedback = _connection_test_feedback(
            form=form,
            result=result,
            action_url=action_url,
            cluster_id=cluster_id,
            provider=provider,
        )

    registration_proof = (
        issue_registration_proof(form=form, user_id=int(current_user.id)) if result.get('connected') else ''
    )
    response = make_response(
        render_template(
            'metrics/partials/_connection_test_result.html',
            connection_feedback=feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    )
    response.headers['HX-Trigger'] = json.dumps(
        {
            'metrics-source-connection-tested': {
                'connected': bool(result.get('connected')),
                'proof': registration_proof,
            }
        },
        separators=(',', ':'),
    )
    return response


def _invalid_form_feedback(
    *,
    action_url: str,
    cluster_id: str,
    draft_name: str,
    provider: MetricsProviderDefinition,
    fields: list[str],
    queue_feedback: bool,
):
    return record_operational_activity(
        user_id=current_user.id,
        event_type='metrics_source_create_rejected',
        status='error',
        title=f'{provider.label} connection not registered',
        message='Review the highlighted connection fields before testing or registering this source.',
        detail=f'The submitted form did not satisfy the {provider.label} metrics-source contract.',
        action_url=action_url,
        action_label=f'Review {provider.label} form',
        action_icon=provider.icon,
        metadata={
            'cluster_id': cluster_id or None,
            'metrics_provider_key': provider.key,
            'fields': fields,
            'submitted_name': draft_name,
            'registration_stage': 'form_validation',
        },
        queue_feedback=queue_feedback,
    )


def _pre_save_connection_failure(
    *,
    connection_test: dict,
    action_url: str,
    cluster_id: str,
    draft_name: str,
    provider: MetricsProviderDefinition,
    queue_feedback: bool,
):
    return record_operational_activity(
        user_id=current_user.id,
        event_type='metrics_source_create_rejected',
        status='error',
        title=f'{provider.label} connection not registered',
        message='The connection changed or became unavailable before registration completed.',
        detail=(
            connection_test.get('error')
            or connection_test.get('reason')
            or 'Review endpoint, authentication, TLS, and compatibility settings.'
        ),
        action_url=action_url,
        action_label=f'Review {provider.label} form',
        action_icon=provider.icon,
        metadata={
            'cluster_id': cluster_id or None,
            'metrics_provider_key': provider.key,
            'failure_code': connection_test.get('failure_code'),
            'endpoint_host': connection_test.get('endpoint_host'),
            'request_path': connection_test.get('request_path'),
            'submitted_name': draft_name,
            'registration_stage': 'pre_save_recheck',
        },
        queue_feedback=queue_feedback,
    )


def _persistence_failure(
    *,
    action_url: str,
    cluster_id: str,
    draft_name: str,
    provider: MetricsProviderDefinition,
    detail: str,
    stage: str,
    queue_feedback: bool,
    reason: str | None = None,
):
    metadata = {
        'cluster_id': cluster_id or None,
        'metrics_provider_key': provider.key,
        'submitted_name': draft_name,
        'registration_stage': stage,
    }
    if reason:
        metadata['reason'] = reason
    return record_operational_activity(
        user_id=current_user.id,
        event_type='metrics_source_create_failed' if reason else 'metrics_source_create_rejected',
        status='error',
        title=f'{provider.label} connection not registered',
        message=f'KAORI could not save the {provider.label} metrics source.',
        detail=detail,
        action_url=action_url,
        action_label=f'Review {provider.label} form',
        action_icon=provider.icon,
        metadata=metadata,
        queue_feedback=queue_feedback,
    )


def _connection_test_invalid_feedback(
    *,
    form: MetricsSourceForm,
    action_url: str,
    cluster_id: str,
    provider: MetricsProviderDefinition,
):
    return record_operational_activity(
        user_id=current_user.id,
        event_type='metrics_source_connection_test_failed',
        status='error',
        title=f'{provider.label} connection test failed',
        message='Review the highlighted connection fields before testing this source.',
        detail=f'The submitted form did not satisfy the {provider.label} metrics-source contract.',
        action_url=action_url,
        action_label=f'Review {provider.label} form',
        action_icon=provider.icon,
        metadata={
            'cluster_id': cluster_id or None,
            'metrics_provider_key': provider.key,
            'fields': sorted(form.errors),
            'draft_connection': True,
            'registration_stage': 'connection_test_form_validation',
        },
        queue_feedback=False,
    )


def _connection_test_feedback(
    *,
    form: MetricsSourceForm,
    result: dict,
    action_url: str,
    cluster_id: str,
    provider: MetricsProviderDefinition,
):
    connected = bool(result.get('connected'))
    detail = (
        f'{str(result.get("endpoint_product") or provider.label).title()} '
        f'{result.get("version") or "unknown"} responded in '
        f'{result.get("response_time_ms") or 0} ms. Register the connection, then run Full Validation.'
        if connected
        else result.get('error')
        or result.get('reason')
        or 'Review endpoint, authentication, TLS, compatibility, and network reachability.'
    )
    return record_operational_activity(
        user_id=current_user.id,
        event_type='metrics_source_connection_test' if connected else 'metrics_source_connection_test_failed',
        status='success' if connected else 'error',
        title=f'{provider.label} connection verified' if connected else f'{provider.label} connection test failed',
        message=(
            f'KAORI reached the submitted {provider.label} metrics endpoint.'
            if connected
            else f'KAORI could not verify the submitted {provider.label} metrics endpoint.'
        ),
        detail=detail,
        action_url=action_url,
        action_label=f'Review {provider.label} form',
        action_icon=provider.icon,
        metadata={
            'cluster_id': cluster_id or None,
            'metrics_provider_key': provider.key,
            'metrics_adapter_key': provider.adapter_key,
            'metrics_query_language': provider.query_language,
            'endpoint_host': result.get('endpoint_host'),
            'endpoint_port': result.get('endpoint_port'),
            'endpoint_product': result.get('endpoint_product'),
            'version': result.get('version'),
            'compatibility_profile': result.get('compatibility_profile'),
            'response_time_ms': result.get('response_time_ms'),
            'failure_code': result.get('failure_code'),
            'request_path': result.get('request_path'),
            'draft_connection': True,
            'submitted_name': (form.name.data or '').strip() or f'Draft {provider.label} connection',
        },
        queue_feedback=False,
    )


def _apply_provider_contract(form: MetricsSourceForm, provider: MetricsProviderDefinition) -> None:
    form.provider_key.data = provider.key
    form.version_detection_mode.data = provider.version_detection_mode


def _registration_url(provider_key: str, *, cluster_id: str = '') -> str:
    return url_for(
        'integrations.register_metrics_source',
        provider_key=provider_key,
        cluster_id=cluster_id or None,
    )


def _provider_or_404(provider_key: str) -> MetricsProviderDefinition:
    try:
        return provider_definition(provider_key)
    except ValueError:
        abort(404)


def _htmx_redirect(location: str) -> ResponseReturnValue:
    response = make_response('', 204)
    response.headers['HX-Redirect'] = location
    return response
