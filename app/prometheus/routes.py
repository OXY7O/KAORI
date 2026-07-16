from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.cluster.service import get_cluster_by_id
from app.common.integration_errors import describe_integration_failure
from app.models import Cluster
from app.notifications.service import (
    get_navigation_notification_context,
    record_operational_activity,
)
from app.prometheus.exceptions import PrometheusError
from app.prometheus.forms import PrometheusConfigForm
from app.prometheus.service import PrometheusService
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

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

    config = cluster.prometheus_config

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

    return render_template(
        'prometheus/config.html',
        cluster=cluster,
        config=config,
        form=form,
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
                'components/navigation/_quick_sync_result.html',
                **feedback,
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify(result)

    except PrometheusError as exc:
        config = cluster.prometheus_config
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
                'components/navigation/_quick_sync_result.html',
                **feedback,
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
                'components/navigation/_quick_sync_result.html',
                **feedback,
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
        result = PrometheusService(cluster).validate_integration()
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
                'components/navigation/_quick_sync_result.html',
                **feedback,
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify(result)

    except PrometheusError as exc:
        config = cluster.prometheus_config
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
                'components/navigation/_quick_sync_result.html',
                **feedback,
                notification_context=get_navigation_notification_context(
                    user_id=current_user.id,
                ),
            )

        return jsonify({'success': False, 'error': failure['detail']}), 400
