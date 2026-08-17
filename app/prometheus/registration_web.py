from __future__ import annotations

import json
import logging

from flask import abort, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.cluster.service import get_cluster_by_id
from app.common.http import is_htmx_request
from app.integrations.prometheus.exceptions import PrometheusError
from app.notifications.service import get_navigation_notification_context, record_operational_activity
from app.prometheus.forms import PrometheusInstanceForm
from app.prometheus.registration import issue_registration_proof, verify_registration_proof
from app.prometheus.service import save_prometheus_instance, test_prometheus_form_connection

logger = logging.getLogger(__name__)


def new_instance_response(*, source_type_override: str | None = None) -> ResponseReturnValue:
    cluster_id = request.values.get('cluster_id', '').strip()
    source_type = str(source_type_override or request.values.get('source_type') or 'prometheus').strip().lower()
    if source_type not in {'prometheus', 'thanos'}:
        abort(400)
    source_label = _source_label(source_type)
    initial_cluster = get_cluster_by_id(cluster_id) if cluster_id else None
    form = PrometheusInstanceForm()
    form.source_type.data = source_type
    form.version_detection_mode.data = 'manual' if source_type == 'thanos' else 'automatic'
    if request.method == 'GET':
        form.enabled.data = True
        form.verify_ssl.data = True

    operation_feedback = None
    if request.method == 'POST':
        response, operation_feedback = _register_submitted_source(
            form=form,
            cluster_id=cluster_id,
            source_type=source_type,
            source_label=source_label,
            initial_cluster=initial_cluster,
        )
        if response is not None:
            return response

    return render_template(
        'prometheus/instance_form.html',
        form=form,
        instance=None,
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
    form: PrometheusInstanceForm,
    cluster_id: str,
    source_type: str,
    source_label: str,
    initial_cluster,
) -> tuple[ResponseReturnValue | None, object | None]:
    is_htmx = is_htmx_request()
    action_url = _registration_url(source_type, cluster_id=cluster_id)
    draft_name = (form.name.data or '').strip() or f'Draft {source_label} connection'
    if not form.validate_on_submit():
        return None, _invalid_form_feedback(
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            source_label=source_label,
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
            event_type='prometheus_instance_create_rejected',
            status='error',
            title='Connection test required',
            message=f'Run Test Connection successfully before registering the {source_label} connection.',
            detail=proof_error,
            action_url=action_url,
            action_label=f'Review {source_label} form',
            action_icon='chart-spline',
            metadata={
                'cluster_id': cluster_id or None,
                'submitted_name': draft_name,
                'metrics_source_type': source_type,
                'registration_stage': 'connection_test_proof',
            },
            queue_feedback=not is_htmx,
        )

    connection_test = test_prometheus_form_connection(form)
    if not connection_test.get('connected'):
        return None, _pre_save_connection_failure(
            connection_test=connection_test,
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            source_type=source_type,
            source_label=source_label,
            queue_feedback=not is_htmx,
        )

    try:
        instance = save_prometheus_instance(form, initial_cluster=initial_cluster)
    except PrometheusError as exc:
        return None, _persistence_failure(
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            source_label=source_label,
            detail=str(exc),
            stage='persistence_validation',
            queue_feedback=not is_htmx,
        )
    except Exception as exc:
        logger.exception('%s metrics-source creation failed.', source_label)
        return None, _persistence_failure(
            action_url=action_url,
            cluster_id=cluster_id,
            draft_name=draft_name,
            source_label=source_label,
            detail='Review KAORI logs and database connectivity before retrying.',
            stage='database_commit',
            reason=type(exc).__name__,
            queue_feedback=not is_htmx,
        )

    record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_instance_created',
        status='success',
        title=f'{source_label} connection registered',
        message=f'{instance.name} is now registered as a reusable {source_label} source.',
        detail=(
            'Reachability and compatibility passed during registration. Run Full Validation, '
            'review readiness, then create scope bindings before operational use.'
        ),
        action_url=url_for('prometheus.instance_detail', instance_id=instance.id),
        action_label=f'Open {source_label} integration',
        action_icon='chart-spline',
        metadata={
            'instance_id': instance.id,
            'cluster_id': cluster_id or None,
            'metrics_source_type': source_type,
            'connection_response_time_ms': connection_test.get('response_time_ms'),
            'detected_version': connection_test.get('version'),
            'endpoint_product': connection_test.get('endpoint_product'),
        },
        queue_feedback=True,
    )
    location = url_for('prometheus.instance_detail', instance_id=instance.id)
    return (_htmx_redirect(location) if is_htmx else redirect(location)), None


def test_new_instance_connection_response(*, source_type_override: str | None = None) -> ResponseReturnValue:
    form = PrometheusInstanceForm()
    cluster_id = request.form.get('cluster_id', '').strip()
    source_type = str(source_type_override or form.source_type.data or 'prometheus').strip().lower()
    if source_type not in {'prometheus', 'thanos'}:
        abort(400)
    form.source_type.data = source_type
    form.version_detection_mode.data = 'manual' if source_type == 'thanos' else 'automatic'
    source_label = _source_label(source_type)
    action_url = _registration_url(source_type, cluster_id=cluster_id)

    if not form.validate_on_submit():
        result = {'connected': False}
        feedback = _connection_test_invalid_feedback(
            form=form,
            action_url=action_url,
            cluster_id=cluster_id,
            source_type=source_type,
            source_label=source_label,
        )
    else:
        result = test_prometheus_form_connection(form)
        feedback = _connection_test_feedback(
            form=form,
            result=result,
            action_url=action_url,
            cluster_id=cluster_id,
            source_type=source_type,
            source_label=source_label,
        )

    registration_proof = (
        issue_registration_proof(form=form, user_id=int(current_user.id)) if result.get('connected') else ''
    )
    response = make_response(
        render_template(
            'prometheus/partials/_connection_test_result.html',
            connection_feedback=feedback,
            notification_context=get_navigation_notification_context(user_id=int(current_user.id)),
        )
    )
    response.headers['HX-Trigger'] = json.dumps(
        {
            'prometheus-connection-tested': {
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
    source_label: str,
    fields: list[str],
    queue_feedback: bool,
):
    return record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_instance_create_rejected',
        status='error',
        title=f'{source_label} connection not registered',
        message='Review the highlighted connection fields before testing or registering this source.',
        detail=f'The submitted form did not satisfy the {source_label} connection contract.',
        action_url=action_url,
        action_label=f'Review {source_label} form',
        action_icon='chart-spline',
        metadata={
            'cluster_id': cluster_id or None,
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
    source_type: str,
    source_label: str,
    queue_feedback: bool,
):
    return record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_instance_create_rejected',
        status='error',
        title=f'{source_label} connection not registered',
        message='The connection changed or became unavailable before registration completed.',
        detail=(
            connection_test.get('error')
            or connection_test.get('reason')
            or 'Review endpoint, authentication, TLS, and compatibility settings.'
        ),
        action_url=action_url,
        action_label=f'Review {source_label} form',
        action_icon='chart-spline',
        metadata={
            'cluster_id': cluster_id or None,
            'metrics_source_type': source_type,
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
    source_label: str,
    detail: str,
    stage: str,
    queue_feedback: bool,
    reason: str | None = None,
):
    metadata = {
        'cluster_id': cluster_id or None,
        'metrics_source_type': 'thanos' if source_label == 'Thanos Query' else 'prometheus',
        'submitted_name': draft_name,
        'registration_stage': stage,
    }
    if reason:
        metadata['reason'] = reason
    return record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_instance_create_failed' if reason else 'prometheus_instance_create_rejected',
        status='error',
        title=f'{source_label} connection not registered',
        message=f'KAORI could not save the {source_label} connection.',
        detail=detail,
        action_url=action_url,
        action_label=f'Review {source_label} form',
        action_icon='chart-spline',
        metadata=metadata,
        queue_feedback=queue_feedback,
    )


def _connection_test_invalid_feedback(
    *,
    form: PrometheusInstanceForm,
    action_url: str,
    cluster_id: str,
    source_type: str,
    source_label: str,
):
    return record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_connection_test_failed',
        status='error',
        title=f'{source_label} connection test failed',
        message='Review the highlighted connection fields before testing this source.',
        detail=f'The submitted form did not satisfy the {source_label} connection contract.',
        action_url=action_url,
        action_label=f'Review {source_label} form',
        action_icon='chart-spline',
        metadata={
            'cluster_id': cluster_id or None,
            'metrics_source_type': source_type,
            'fields': sorted(form.errors),
            'draft_connection': True,
            'registration_stage': 'connection_test_form_validation',
        },
        queue_feedback=False,
    )


def _connection_test_feedback(
    *,
    form: PrometheusInstanceForm,
    result: dict,
    action_url: str,
    cluster_id: str,
    source_type: str,
    source_label: str,
):
    connected = bool(result.get('connected'))
    detail = (
        f'{str(result.get("endpoint_product") or source_label).title()} '
        f'{result.get("version") or "unknown"} responded in '
        f'{result.get("response_time_ms") or 0} ms. Register the connection, then run Full Validation.'
        if connected
        else result.get('error')
        or result.get('reason')
        or 'Review endpoint, authentication, TLS, compatibility, and network reachability.'
    )
    return record_operational_activity(
        user_id=current_user.id,
        event_type='prometheus_connection_test' if connected else 'prometheus_connection_test_failed',
        status='success' if connected else 'error',
        title=f'{source_label} connection verified' if connected else f'{source_label} connection test failed',
        message=(
            f'KAORI reached the submitted {source_label} endpoint.'
            if connected
            else f'KAORI could not verify the submitted {source_label} endpoint.'
        ),
        detail=detail,
        action_url=action_url,
        action_label=f'Review {source_label} form',
        action_icon='chart-spline',
        metadata={
            'cluster_id': cluster_id or None,
            'metrics_source_type': source_type,
            'endpoint_host': result.get('endpoint_host'),
            'endpoint_port': result.get('endpoint_port'),
            'endpoint_product': result.get('endpoint_product'),
            'version': result.get('version'),
            'compatibility_profile': result.get('compatibility_profile'),
            'response_time_ms': result.get('response_time_ms'),
            'failure_code': result.get('failure_code'),
            'request_path': result.get('request_path'),
            'draft_connection': True,
            'submitted_name': (form.name.data or '').strip() or f'Draft {source_label} connection',
        },
        queue_feedback=False,
    )


def _registration_url(source_type: str, *, cluster_id: str = '') -> str:
    endpoint = (
        'integrations.register_thanos_metrics_source'
        if source_type == 'thanos'
        else 'integrations.register_prometheus_metrics_source'
    )
    return url_for(endpoint, cluster_id=cluster_id or None)


def _source_label(source_type: str) -> str:
    return 'Thanos Query' if source_type == 'thanos' else 'Prometheus'


def _htmx_redirect(location: str) -> ResponseReturnValue:
    response = make_response('', 204)
    response.headers['HX-Redirect'] = location
    return response
