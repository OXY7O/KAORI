"""GitHub App integration lifecycle candidate (SC-02 #2741).

Deliberately NOT registered in the canonical Integration Kernel yet. Job
admission, completed provider UI and multi-installation UAT must be accepted
before GitHub can transition from the planned provider matrix state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.lifecycle import ensure_provider_operational
from app.integrations.runtime.scoring import calculate_health
from app.integrations.source_control.source_control.providers.github.credential_service import (
    build_client_for_installation,
    probe_installation,
)
from app.integrations.source_control.source_control.providers.github.readiness import assess_installation_readiness
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.models.source_control import SourceInstallation

_PROFILE = 'github-app-readiness-v1'


def _account_id(instance: SourceInstallation) -> str:
    if instance.account is None:
        raise GitHubProviderError('GitHub installation account identity is unavailable.')
    return str(instance.account.native_account_id)


def _canonical(instance: SourceInstallation):
    return ensure_provider_operational(instance, integration_type='source_control')


class GitHubRuntimeAdapter:
    integration_type = 'source_control'

    def execute(self, operation: str, instance: SourceInstallation, **kwargs: Any) -> Any:
        if operation == 'connection.test':
            _canonical(instance)
            evidence = probe_installation(instance)
            return {
                'connected': True,
                'installation_id': evidence.installation_id,
                'account_id': evidence.account_id,
                'repository_scope': evidence.repository_selection,
                'observed_at': evidence.observed_at.isoformat(),
            }
        if operation == 'runtime.validate':
            return self.refresh(instance)
        if operation == 'runtime.health':
            return self.refresh_health(instance)
        if operation == 'runtime.state':
            return self.get_state(instance, validation_result=kwargs.get('validation_result'))
        raise ValueError('Unsupported Source Control integration operation.')

    def refresh(self, instance: SourceInstallation) -> dict[str, Any]:
        """Full Validation candidate; permission coverage != committed inventory."""
        canonical = _canonical(instance)
        now = datetime.now(UTC)
        try:
            observation = probe_installation(instance)
            assessment = assess_installation_readiness(observation)
        except GitHubProviderError:
            canonical.readiness_status = 'blocked'
            canonical.health_status = 'unhealthy'
            canonical.last_error = 'GitHub App installation authentication or scope validation failed.'
            canonical.last_checked_at = now
            db.session.commit()
            return {
                'connected': False,
                'readiness_status': 'blocked',
                'reason': 'GitHub App installation authentication or scope validation failed.',
            }

        canonical.readiness_status = assessment.status
        canonical.health_status = 'healthy' if assessment.status != 'blocked' else 'degraded'
        canonical.last_error = None
        canonical.last_checked_at = now
        canonical.metadata_json = {
            **(canonical.metadata_json or {}),
            'github_validation': {
                'profile': _PROFILE,
                'repository_scope': assessment.repository_scope,
                'coverage_hint': assessment.coverage_hint,
                'grant_count_hint': observation.granted_repository_count,
                'capability_states': dict(assessment.capability_states),
                'last_validated_at': observation.observed_at.isoformat(),
            },
        }
        instance.repository_scope = observation.repository_selection
        instance.last_observed_at = observation.observed_at
        db.session.commit()
        return {
            'connected': True,
            'readiness_status': assessment.status,
            'capabilities': assessment.capability_states,
            'repository_scope': assessment.repository_scope,
            'reason': assessment.reason,
        }

    def refresh_health(self, instance: SourceInstallation) -> dict[str, Any]:
        """Lightweight App/installation check; preserves full capability evidence."""
        canonical = _canonical(instance)
        now = datetime.now(UTC)
        try:
            client = build_client_for_installation(instance)
            client.installation_detail(instance.native_installation_id, _account_id(instance))
        except GitHubProviderError:
            canonical.health_status = 'unhealthy'
            canonical.readiness_status = 'blocked'
            canonical.last_error = 'GitHub App installation is inaccessible or suspended.'
        else:
            canonical.health_status = 'healthy'
            canonical.last_error = None
        canonical.last_checked_at = now
        db.session.commit()
        return {'health_status': canonical.health_status}

    def get_state(self, instance: SourceInstallation, *, validation_result: Any = None) -> RuntimeState:
        canonical = instance.integration_instance
        now = datetime.now(UTC)
        status = str(canonical.health_status or 'not_observed')
        is_healthy = status == 'healthy'
        unknown = status == 'not_observed'
        qualified = canonical.readiness_status == 'ready'
        health = calculate_health(
            (
                HealthFactor(
                    'provider_health',
                    'GitHub App Health',
                    'success' if is_healthy else ('unknown' if unknown else 'failed'),
                    60,
                    100 if is_healthy else (50 if unknown else 0),
                ),
                HealthFactor(
                    'validation',
                    'Full Validation',
                    'success' if qualified else 'warning',
                    40,
                    100 if qualified else 50,
                ),
            )
        )
        metadata = (canonical.metadata_json or {}).get('github_validation') or {}
        safe = metadata if isinstance(metadata, dict) else {}
        return RuntimeState(
            integration_type=self.integration_type,
            provider_key='github',
            adapter_key='github_rest_v3',
            instance_id=str(instance.id),
            instance_name=canonical.name,
            observed_at=canonical.last_checked_at or now,
            readiness=canonical.readiness_status or 'validation_required',
            health=health,
            diagnostics=(
                DiagnosticResult(
                    key='installation_auth',
                    label='Installation Scope',
                    category='runtime',
                    status='success' if is_healthy else ('unknown' if unknown else 'failed'),
                    detail='GitHub App installation is reachable.'
                    if is_healthy
                    else 'Installation state requires operator review.',
                ),
            ),
            snapshot=CapabilitySnapshot(
                profile=str(safe.get('profile') or _PROFILE),
                compatibility_profile=None,
                capabilities=tuple(
                    key
                    for key, value in dict(safe.get('capability_states') or {}).items()
                    if value == 'permission_verified'
                ),
                observed_at=instance.last_observed_at or now,
                metadata={
                    'repository_scope': str(safe.get('repository_scope') or 'unknown'),
                    'coverage_hint': str(safe.get('coverage_hint') or 'unverified'),
                },
            ),
            last_success_at=canonical.last_checked_at if is_healthy else None,
            last_failure_at=canonical.last_checked_at if status == 'unhealthy' else None,
            latency_ms=None,
            message=canonical.last_error or 'Complete GitHub App admission and validation.',
        )


runtime_adapter = GitHubRuntimeAdapter()
