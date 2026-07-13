from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.alertmanager.forms import parse_alertmanager_config_form
from app.alertmanager.service import (
    build_alertmanager_config_context,
    get_alertmanager_config_by_cluster_id,
    get_cluster_by_id,
    save_alertmanager_config,
    test_alertmanager_connection,
)
from app.notifications.queries import get_navigation_notification_context
from app.notifications.writer import record_operational_activity
from app.rbac.decorators import permission_required

logger = logging.getLogger(__name__)

alertmanager_bp = Blueprint(
    'alertmanager',
    __name__,
    url_prefix='/alertmanager',
)


@alertmanager_bp.route(
    '/cluster/<string:cluster_id>',
    methods=[
        'GET',
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def cluster_alertmanager_config(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(
            404,
        )

    if request.method == 'POST':
        form = parse_alertmanager_config_form(
            request.form,
        )

        if not form.endpoint:
            record_operational_activity(
                user_id=current_user.id,
                event_type='alertmanager_configuration_create',
                status='error',
                title='Alertmanager configuration not saved',
                message='Alertmanager endpoint is required.',
                detail='Provide a valid Alertmanager endpoint before saving the integration.',
                action_url=url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id),
                action_label='Review Alertmanager settings',
                action_icon='siren',
                metadata={
                    'cluster_id': cluster.id,
                    'cluster_name': cluster.name,
                    'reason': 'missing_endpoint',
                },
                queue_feedback=True,
            )
        else:
            existing_config = get_alertmanager_config_by_cluster_id(
                cluster_id,
            )
            was_configured = bool(existing_config and existing_config.endpoint)
            try:
                saved_config = save_alertmanager_config(
                    cluster_id=cluster_id,
                    form=form,
                )
            except Exception as exc:
                logger.exception(
                    'Alertmanager configuration save failed for cluster %s.',
                    cluster.id,
                )
                record_operational_activity(
                    user_id=current_user.id,
                    event_type='alertmanager_configuration_update' if was_configured else 'alertmanager_configuration_create',
                    status='error',
                    title='Alertmanager configuration not saved',
                    message=f'KAORI could not save Alertmanager settings for {cluster.name}.',
                    detail='Review application logs, submitted values, and database connectivity before retrying.',
                    action_url=url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id),
                    action_label='Review Alertmanager settings',
                    action_icon='siren',
                    metadata={
                        'cluster_id': cluster.id,
                        'cluster_name': cluster.name,
                        'reason': type(exc).__name__,
                    },
                    queue_feedback=True,
                )
            else:
                action = request.form.get(
                    'action',
                    'save',
                )

                if action == 'save_test':
                    result = test_alertmanager_connection(
                        cluster_id=cluster_id,
                    )

                    if result.get(
                        'connected',
                        False,
                    ):
                        record_operational_activity(
                            user_id=current_user.id,
                            event_type='alertmanager_configuration_update' if was_configured else 'alertmanager_configuration_create',
                            status='success',
                            title='Alertmanager saved and verified',
                            message=f'Alertmanager settings for {cluster.name} were saved and the connection test succeeded.',
                            detail=f'Alertmanager version {result.get("version") or "unknown"} responded in {result.get("response_time_ms") or 0} ms.',
                            action_url=url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id),
                            action_label='View Alertmanager settings',
                            action_icon='siren',
                            metadata={
                                'cluster_id': cluster.id,
                                'cluster_name': cluster.name,
                                'endpoint': saved_config.endpoint,
                                'auth_type': saved_config.auth_type,
                                'timeout_seconds': saved_config.timeout,
                                'verify_ssl': saved_config.verify_ssl,
                                'version': result.get('version') or 'unknown',
                                'response_time_ms': result.get('response_time_ms') or 0,
                            },
                            queue_feedback=True,
                        )
                    else:
                        record_operational_activity(
                            user_id=current_user.id,
                            event_type='alertmanager_configuration_update' if was_configured else 'alertmanager_configuration_create',
                            status='warning',
                            title='Alertmanager saved with warning',
                            message=f'Alertmanager settings for {cluster.name} were saved, but the connection test failed.',
                            detail=result.get('error') or 'Review endpoint reachability, authentication, and TLS settings.',
                            action_url=url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id),
                            action_label='Review Alertmanager settings',
                            action_icon='siren',
                            metadata={
                                'cluster_id': cluster.id,
                                'cluster_name': cluster.name,
                                'endpoint': saved_config.endpoint,
                                'auth_type': saved_config.auth_type,
                                'timeout_seconds': saved_config.timeout,
                                'verify_ssl': saved_config.verify_ssl,
                                'test_connected': False,
                                'reason': result.get('reason') or 'Connection failed',
                                'failure_code': result.get('failure_code') or 'connection_failed',
                                'endpoint_host': result.get('endpoint_host'),
                                'endpoint_port': result.get('endpoint_port'),
                                'request_path': result.get('request_path'),
                            },
                            queue_feedback=True,
                        )
                else:
                    record_operational_activity(
                        user_id=current_user.id,
                        event_type='alertmanager_configuration_update' if was_configured else 'alertmanager_configuration_create',
                        status='success',
                        title='Alertmanager configuration updated' if was_configured else 'Alertmanager configured',
                        message=f'Alertmanager settings for {cluster.name} were saved successfully.',
                        detail='KAORI will use the saved endpoint, authentication method, timeout, and TLS verification settings for alert retrieval.',
                        action_url=url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id),
                        action_label='View Alertmanager settings',
                        action_icon='siren',
                        metadata={
                            'cluster_id': cluster.id,
                            'cluster_name': cluster.name,
                            'endpoint': saved_config.endpoint,
                            'auth_type': saved_config.auth_type,
                            'timeout_seconds': saved_config.timeout,
                            'verify_ssl': saved_config.verify_ssl,
                        },
                        queue_feedback=True,
                    )

                return redirect(
                    url_for(
                        'alertmanager.cluster_alertmanager_config',
                        cluster_id=cluster_id,
                    )
                )

    context = build_alertmanager_config_context(
        cluster_id=cluster_id,
    )

    return render_template(
        'alertmanager/config.html',
        **context,
    )


@alertmanager_bp.route(
    '/cluster/<string:cluster_id>/test',
    methods=[
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def test_cluster_alertmanager(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(
            404,
        )

    result = test_alertmanager_connection(
        cluster_id=cluster_id,
    )

    if result.get('connected', False):
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='alertmanager_connection_test',
            status='success',
            title='Alertmanager connection verified',
            message=f'KAORI connected to Alertmanager for {cluster.name}.',
            detail=f'Alertmanager version {result.get("version") or "unknown"} responded in {result.get("response_time_ms") or 0} ms.',
            action_url=url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id),
            action_label='View Alertmanager settings',
            action_icon='siren',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'version': result.get('version') or 'unknown',
                'response_time_ms': result.get('response_time_ms') or 0,
            },
        )
    else:
        feedback = record_operational_activity(
            user_id=current_user.id,
            event_type='alertmanager_connection_test',
            status='error',
            title='Alertmanager connection failed',
            message=f'KAORI could not connect to Alertmanager for {cluster.name}.',
            detail=result.get('error') or 'Review endpoint reachability, authentication, and TLS settings.',
            action_url=url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id),
            action_label='Review Alertmanager settings',
            action_icon='siren',
            metadata={
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'reason': result.get('reason') or 'Connection failed',
                'failure_code': result.get('failure_code') or 'connection_failed',
                'endpoint_host': result.get('endpoint_host'),
                'endpoint_port': result.get('endpoint_port'),
                'request_path': result.get('request_path'),
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
            'success': result.get(
                'connected',
                False,
            ),
            'version': result.get(
                'version',
                'unknown',
            ),
            'response_time_ms': result.get(
                'response_time_ms',
                0,
            ),
            'error': result.get(
                'error',
            ),
            'reason': result.get(
                'reason',
            ),
            'failure_code': result.get(
                'failure_code',
            ),
        }
    )
