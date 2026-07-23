from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.common.integration_errors import describe_integration_failure
from app.extensions import db
from app.integrations.alertmanager.client_factory import build_client
from app.integrations.alertmanager.contracts import ValidationResult, ValidationStep
from app.integrations.alertmanager.exceptions import AlertmanagerError
from app.integrations.alertmanager.probes import discover_payload_capabilities
from app.integrations.alertmanager.profiles import resolve_profile
from app.integrations.alertmanager.requirements import evaluate_module_readiness
from app.integrations.alertmanager.status import mark_status
from app.integrations.compatibility import evaluate_compatibility
from app.models.alertmanager import AlertmanagerInstance

logger = logging.getLogger(__name__)


def validate_source(source: AlertmanagerInstance, *, source_label: str) -> ValidationResult:
    if not source.endpoint:
        return ValidationResult(
            connected=False,
            label='Alertmanager Not Configured',
            error='Alertmanager endpoint is not configured.',
            reason='Integration is not configured',
            failure_code='not_configured',
        )

    client = build_client(source)
    steps: list[ValidationStep] = []
    try:
        connection = client.test_connection()
        steps.append(ValidationStep('status_v2', 'Status API', 'success', 'Alertmanager status and build information are readable.', int(connection.get('response_time_ms') or 0)))
    except AlertmanagerError as exc:
        return _failure(source, exc, source_label=source_label, unexpected=False)
    except Exception as exc:  # pragma: no cover
        return _failure(source, exc, source_label=source_label, unexpected=True)

    capabilities = {'status_v2'}
    alerts: list[dict[str, Any]] = []
    silences: list[dict[str, Any]] = []
    capability_errors: list[str] = []
    for capability, label, operation in (
        ('alerts_v2', 'Alerts API', client.get_alerts),
        ('silences_v2', 'Silences API', client.get_silences),
    ):
        try:
            payload = operation()
            if capability == 'alerts_v2':
                alerts = payload if isinstance(payload, list) else []
            else:
                silences = payload if isinstance(payload, list) else []
            capabilities.add(capability)
            steps.append(ValidationStep(capability, label, 'success', f'{label} is readable.'))
        except AlertmanagerError as exc:
            capability_errors.append(f'{capability}: {exc}')
            steps.append(ValidationStep(capability, label, 'failed', str(exc)))
            logger.warning('%s capability probe failed for %s: %s', capability, source_label, exc)

    capabilities.update(discover_payload_capabilities(alerts, silences))
    version = str(connection.get('version') or 'unknown')
    compatibility = evaluate_compatibility('alertmanager', version, capabilities=capabilities)
    profile = resolve_profile(version)
    capability_profile = profile.key if profile else 'alertmanager-unmapped'
    module_readiness = evaluate_module_readiness(capabilities)

    message = compatibility.message
    if capability_errors and compatibility.readiness != 'blocked':
        message = f'{message} Capability warnings: {"; ".join(capability_errors)}'

    source.detected_version = version
    source.compatibility_status = compatibility.status
    source.compatibility_profile = compatibility.profile_key
    source.capability_profile = capability_profile
    if hasattr(source, 'capabilities'):
        setattr(source, 'capabilities', sorted(capabilities))
    source.readiness_status = compatibility.readiness
    source.validation_message = message
    source.last_validated_at = datetime.now(UTC)
    mark_status(source, status='connected' if compatibility.readiness != 'blocked' else 'incompatible', error=None if compatibility.readiness != 'blocked' else message, response_time_ms=int(connection.get('response_time_ms') or 0), commit=False)
    db.session.commit()

    steps.append(ValidationStep('compatibility', 'Compatibility Profile', 'success' if compatibility.readiness != 'blocked' else 'failed', f'{capability_profile}: {message}'))
    return ValidationResult(
        connected=compatibility.readiness != 'blocked',
        label='Alertmanager Ready' if compatibility.readiness == 'ready' else 'Alertmanager Requires Attention',
        response_time_ms=int(connection.get('response_time_ms') or 0),
        version=version,
        compatibility_status=compatibility.status,
        readiness_status=compatibility.readiness,
        compatibility_profile=compatibility.profile_key,
        capabilities=tuple(sorted(capabilities)),
        capability_profile=capability_profile,
        validation_steps=tuple(steps),
        module_readiness=tuple(module_readiness),
        error=None if compatibility.readiness != 'blocked' else message,
        reason=message,
        failure_code=None if compatibility.readiness != 'blocked' else compatibility.status,
    )


def _failure(source: AlertmanagerInstance, exc: Exception, *, source_label: str, unexpected: bool) -> ValidationResult:
    failure = describe_integration_failure(exc, service_name='Alertmanager', endpoint=source.endpoint, request_path='/api/v2/status', timeout_seconds=min(max(int(source.timeout or 5), 1), 30))
    if unexpected:
        logger.exception('Unexpected Alertmanager validation failure for %s.', source_label)
        status, label = 'error', 'Alertmanager Error'
    else:
        logger.warning('Alertmanager validation failed for %s: %s', source_label, exc, exc_info=True)
        status, label = 'disconnected', 'Alertmanager Disconnected'
    source.readiness_status = 'blocked'
    source.compatibility_status = 'validation_failed'
    source.validation_message = failure['detail']
    source.last_validated_at = datetime.now(UTC)
    mark_status(source, status=status, error=failure['detail'], response_time_ms=None, commit=False)
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
        validation_steps=(ValidationStep('connection', 'Connection', 'failed', failure['detail']),),
    )
