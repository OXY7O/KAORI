from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.common.integration_errors import describe_integration_failure
from app.extensions.db import db
from app.integrations.compatibility import evaluate_compatibility
from app.integrations.registry.providers.harbor.capabilities import CAPABILITY_PROFILE
from app.integrations.registry.providers.harbor.client_factory import build_client
from app.integrations.registry.providers.harbor.contracts import ValidationResult, ValidationStep
from app.integrations.registry.providers.harbor.exceptions import HarborError, HarborResponseError
from app.integrations.registry.providers.harbor.status import mark_status
from app.models.harbor import HarborInstance

logger = logging.getLogger(__name__)


def test_connection(source: HarborInstance) -> dict[str, object]:
    """Prove Harbor endpoint identity without establishing Full Validation readiness."""
    return build_client(source).test_connection()


def validate_source(source: HarborInstance, *, source_label: str) -> ValidationResult:
    if not source.endpoint:
        return ValidationResult(
            connected=False,
            label='Harbor Not Configured',
            error='Harbor endpoint is not configured.',
            reason='Integration is not configured',
            failure_code='not_configured',
        )

    client = build_client(source)
    steps: list[ValidationStep] = []
    capabilities: set[str] = set()

    try:
        connection = client.test_connection()
    except HarborError as exc:
        return _failure(source, exc, source_label=source_label, unexpected=False)
    except Exception as exc:  # pragma: no cover
        return _failure(source, exc, source_label=source_label, unexpected=True)

    capabilities.add('system_identity')
    steps.append(
        ValidationStep(
            'system_identity',
            'System Identity',
            'success',
            'Harbor system information and version identity are readable.',
            int(connection.get('response_time_ms') or 0),
        )
    )

    health_summary: dict[str, object] = {}
    projects: list[dict[str, object]] = []
    project_count = 0
    repository_count = 0

    try:
        health = client.get_health()
        capabilities.add('provider_health')
        health_summary = _health_summary(health)
        overall = str(health_summary.get('status') or 'unknown')
        steps.append(
            ValidationStep(
                'provider_health',
                'Provider Health',
                'success' if overall == 'healthy' else 'warning',
                f'Harbor reports overall health: {overall}.',
            )
        )
    except HarborError as exc:
        steps.append(ValidationStep('provider_health', 'Provider Health', 'failed', str(exc)))
        logger.warning('Harbor health probe failed for %s: %s', source_label, exc)

    try:
        projects = client.list_projects(page=1, page_size=1)
        project_count = len(projects)
        capabilities.add('project_discovery')
        steps.append(
            ValidationStep(
                'project_discovery',
                'Project Discovery',
                'success',
                'Harbor project listing is readable.',
            )
        )
    except HarborError as exc:
        steps.append(ValidationStep('project_discovery', 'Project Discovery', 'failed', str(exc)))
        logger.warning('Harbor project probe failed for %s: %s', source_label, exc)

    try:
        if not projects:
            raise HarborResponseError(
                'Harbor project listing returned no visible project, so repository discovery could not be proven.'
            )
        project_scope = projects[0].get('name') or projects[0].get('project_id')
        if project_scope in {None, ''}:
            raise HarborResponseError(
                'Harbor project evidence did not include a project name or id for repository discovery.'
            )
        repositories = client.list_repositories(
            project_name_or_id=str(project_scope),
            page=1,
            page_size=1,
        )
        repository_count = len(repositories)
        capabilities.add('repository_discovery')
        steps.append(
            ValidationStep(
                'repository_discovery',
                'Repository Discovery',
                'success',
                f'Harbor repository listing is readable for project {project_scope}.',
            )
        )
    except HarborError as exc:
        steps.append(ValidationStep('repository_discovery', 'Repository Discovery', 'failed', str(exc)))
        logger.warning('Harbor repository probe failed for %s: %s', source_label, exc)

    version = str(connection.get('version') or 'unknown')
    compatibility = evaluate_compatibility('harbor', version, capabilities=capabilities)
    message = compatibility.message

    source.detected_version = version
    source.compatibility_status = compatibility.status
    source.compatibility_profile = compatibility.profile_key
    source.capability_profile = CAPABILITY_PROFILE
    source.capabilities = sorted(capabilities)
    source.validation_summary = {
        'provider_health': health_summary,
        'project_probe_count': project_count,
        'repository_probe_count': repository_count,
        'required_capabilities_observed': sorted(capabilities),
    }
    source.readiness_status = compatibility.readiness
    source.validation_message = message
    source.last_validated_at = datetime.now(UTC)
    mark_status(
        source,
        status='connected',
        error=None,
        response_time_ms=int(connection.get('response_time_ms') or 0),
        commit=False,
    )
    db.session.commit()

    steps.append(
        ValidationStep(
            'compatibility',
            'Compatibility Profile',
            'success' if compatibility.readiness == 'ready' else (
                'failed' if compatibility.readiness == 'blocked' else 'warning'
            ),
            f'{compatibility.profile_key or "No profile"}: {message}',
        )
    )

    return ValidationResult(
        connected=True,
        label='Harbor Ready' if compatibility.readiness == 'ready' else 'Harbor Requires Attention',
        response_time_ms=int(connection.get('response_time_ms') or 0),
        version=version,
        compatibility_status=compatibility.status,
        readiness_status=compatibility.readiness,
        compatibility_profile=compatibility.profile_key,
        capabilities=tuple(sorted(capabilities)),
        capability_profile=CAPABILITY_PROFILE,
        validation_steps=tuple(steps),
        error=message if compatibility.readiness == 'blocked' else None,
        reason=message,
        failure_code=compatibility.status if compatibility.readiness == 'blocked' else None,
    )


def _health_summary(payload: dict[str, object]) -> dict[str, object]:
    components = payload.get('components')
    rows: list[dict[str, str]] = []
    if isinstance(components, list):
        for item in components:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    'name': str(item.get('name') or 'unknown'),
                    'status': str(item.get('status') or 'unknown'),
                }
            )
    return {
        'status': str(payload.get('status') or 'unknown'),
        'components': rows,
    }


def _failure(source: HarborInstance, exc: Exception, *, source_label: str, unexpected: bool) -> ValidationResult:
    failure = describe_integration_failure(
        exc,
        service_name='Harbor',
        endpoint=source.endpoint,
        request_path='/api/v2.0/systeminfo',
        timeout_seconds=min(max(int(source.timeout or 5), 1), 30),
    )
    if unexpected:
        logger.exception('Unexpected Harbor validation failure for %s.', source_label)
        status, label = 'error', 'Harbor Error'
    else:
        logger.warning('Harbor validation failed for %s: %s', source_label, exc, exc_info=True)
        status, label = 'disconnected', 'Harbor Disconnected'

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
        endpoint_port=int(failure['endpoint_port']) if failure.get('endpoint_port') else None,
        request_path=failure['request_path'],
        validation_steps=(
            ValidationStep('system_identity', 'System Identity', 'failed', failure['detail']),
        ),
    )
