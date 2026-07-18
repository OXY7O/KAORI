from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.alertmanager.client_factory import build_client
from app.alertmanager.contracts import ValidationResult
from app.alertmanager.exceptions import AlertmanagerError
from app.alertmanager.status import mark_status
from app.common.integration_errors import describe_integration_failure
from app.extensions import db
from app.integrations.compatibility import evaluate_compatibility
from app.models.alertmanager import AlertmanagerConfig, AlertmanagerInstance

logger = logging.getLogger(__name__)


ValidatableAlertmanager = AlertmanagerInstance | AlertmanagerConfig


def validate_source(
    source: ValidatableAlertmanager,
    *,
    source_label: str,
) -> ValidationResult:
    if not source.endpoint:
        return ValidationResult(
            connected=False,
            label='Alertmanager Not Configured',
            error='Alertmanager endpoint is not configured.',
            reason='Integration is not configured',
            failure_code='not_configured',
        )

    client = build_client(source)
    try:
        connection = client.test_connection()
    except AlertmanagerError as exc:
        return _failure(source, exc, source_label=source_label, unexpected=False)
    except Exception as exc:  # pragma: no cover - defensive integration boundary
        return _failure(source, exc, source_label=source_label, unexpected=True)

    capabilities = {'status_v2'}
    capability_errors: list[str] = []
    for capability, operation in (
        ('alerts_v2', client.get_alerts),
        ('silences_v2', client.get_silences),
    ):
        try:
            operation()
            capabilities.add(capability)
        except AlertmanagerError as exc:
            capability_errors.append(f'{capability}: {exc}')
            logger.warning('%s capability probe failed for %s: %s', capability, source_label, exc)

    version = str(connection.get('version') or 'unknown')
    compatibility = evaluate_compatibility(
        'alertmanager',
        version,
        capabilities=capabilities,
    )
    message = compatibility.message
    if capability_errors and compatibility.readiness != 'blocked':
        message = f'{message} Capability warnings: {"; ".join(capability_errors)}'

    source.detected_version = version
    source.compatibility_status = compatibility.status
    source.compatibility_profile = compatibility.profile_key
    source.capability_profile = 'alert-management-v1'
    if hasattr(source, 'capabilities'):
        setattr(source, 'capabilities', sorted(capabilities))
    source.readiness_status = compatibility.readiness
    source.validation_message = message
    source.last_validated_at = datetime.now(UTC)
    mark_status(
        source,
        status='connected' if compatibility.readiness != 'blocked' else 'incompatible',
        error=None if compatibility.readiness != 'blocked' else message,
        response_time_ms=int(connection.get('response_time_ms') or 0),
        commit=False,
    )
    db.session.commit()

    return ValidationResult(
        connected=compatibility.readiness != 'blocked',
        label='Alertmanager Ready' if compatibility.readiness == 'ready' else 'Alertmanager Requires Attention',
        response_time_ms=int(connection.get('response_time_ms') or 0),
        version=version,
        compatibility_status=compatibility.status,
        readiness_status=compatibility.readiness,
        compatibility_profile=compatibility.profile_key,
        capabilities=tuple(sorted(capabilities)),
        error=None if compatibility.readiness != 'blocked' else message,
        reason=message,
        failure_code=None if compatibility.readiness != 'blocked' else compatibility.status,
    )


def _failure(
    source: ValidatableAlertmanager,
    exc: Exception,
    *,
    source_label: str,
    unexpected: bool,
) -> ValidationResult:
    failure = describe_integration_failure(
        exc,
        service_name='Alertmanager',
        endpoint=source.endpoint,
        request_path='/api/v2/status',
        timeout_seconds=min(max(int(source.timeout or 5), 1), 30),
    )
    if unexpected:
        logger.exception('Unexpected Alertmanager validation failure for %s.', source_label)
        status = 'error'
        label = 'Alertmanager Error'
    else:
        logger.warning('Alertmanager validation failed for %s: %s', source_label, exc, exc_info=True)
        status = 'disconnected'
        label = 'Alertmanager Disconnected'

    source.readiness_status = 'blocked'
    source.compatibility_status = 'validation_failed'
    source.validation_message = failure['detail']
    source.last_validated_at = datetime.now(UTC)
    mark_status(
        source,
        status=status,
        error=failure['detail'],
        response_time_ms=None,
        commit=False,
    )
    db.session.commit()
    return ValidationResult(
        connected=False,
        label=label,
        error=failure['detail'],
        reason=failure['reason'],
        failure_code=failure['code'],
        endpoint_host=failure['endpoint_host'],
        endpoint_port=failure['endpoint_port'],
        request_path=failure['request_path'],
    )
