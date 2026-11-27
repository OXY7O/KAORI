"""OpenBao connection health and Full Validation candidate through canonical Kernel."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.contracts import CapabilitySnapshot, DiagnosticResult, HealthFactor, RuntimeState
from app.integrations.lifecycle import ensure_provider_operational
from app.integrations.runtime.scoring import calculate_health
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import (
    connection_values,
    local_provider_enabled,
    verify_connection,
    verify_health,
)
from app.models.openbao import OpenBaoInstance
from app.security.credentials import CredentialEncryptionError


def record_failure(row: OpenBaoInstance, _error: Exception) -> None:
    identity = row.integration_instance
    identity.health_status = 'disconnected'
    identity.readiness_status = 'blocked'
    identity.last_checked_at = datetime.now(UTC)
    identity.last_error = 'OpenBao connection unavailable; review TLS, pinned cluster and scoped AppRole.'


class OpenBaoRuntimeAdapter:
    integration_type = 'secrets_pki'

    def execute(self, operation: str, row: OpenBaoInstance, **kwargs: Any) -> Any:
        if operation == 'runtime.validate':
            return self.refresh(row)
        if operation == 'runtime.health':
            return self.refresh_health(row)
        if operation == 'connection.test':
            self._guard(row)
            verify_connection(connection_values(row))
            return {'connected': True, 'version': '2.7.3'}
        if operation == 'runtime.state':
            return self.get_state(row, validation_result=kwargs.get('validation_result'))
        raise ValueError('OpenBao material access and generic client construction are not admitted.')

    @staticmethod
    def _guard(row: OpenBaoInstance) -> None:
        identity = ensure_provider_operational(row, integration_type='secrets_pki')
        if not local_provider_enabled() or identity.provider_key != 'openbao' or identity.adapter_key != 'openbao_http_v1':
            raise ValueError('OpenBao runtime operations are restricted to local development.')

    def refresh(self, row: OpenBaoInstance) -> dict[str, Any]:
        self._guard(row)
        identity = row.integration_instance
        try:
            verify_connection(connection_values(row))
        except (ValueError, CredentialEncryptionError) as exc:
            record_failure(row, exc)
        else:
            row.detected_version = '2.7.3'
            row.last_validated_at = datetime.now(UTC)
            identity.last_checked_at = row.last_validated_at
            identity.health_status = 'connected'
            identity.readiness_status = 'degraded'
            identity.last_error = None
        db.session.commit()
        return {'connected': identity.health_status == 'connected', 'readiness_status': identity.readiness_status}

    def refresh_health(self, row: OpenBaoInstance) -> dict[str, Any]:
        self._guard(row)
        identity = row.integration_instance
        try:
            verify_health(row)
        except ValueError as exc:
            record_failure(row, exc)
        else:
            identity.health_status = 'connected'
            identity.last_checked_at = datetime.now(UTC)
            identity.last_error = None
        db.session.commit()
        return {'connected': identity.health_status == 'connected', 'readiness_status': identity.readiness_status}

    def get_state(self, row: OpenBaoInstance, *, validation_result: Any = None) -> RuntimeState:
        identity = row.integration_instance
        available = (
            identity.health_status == 'connected'
            and local_provider_enabled()
            and identity.enabled
            and identity.lifecycle_status == 'active'
        )
        now = datetime.now(UTC)
        return RuntimeState(
            integration_type='secrets_pki',
            provider_key='openbao',
            adapter_key='openbao_http_v1',
            instance_id=f'openbao:{row.id}',
            instance_name=row.name,
            observed_at=identity.last_checked_at or now,
            readiness=(identity.readiness_status or 'validation_required') if available else 'blocked',
            health=calculate_health((
                HealthFactor('connection', 'OpenBao Connection', 'success' if available else 'failed', 50, 100 if available else 0),
                HealthFactor('authority', 'Credential Authority', 'warning', 50, 50),
            )),
            diagnostics=(
                DiagnosticResult(
                    key='openbao_connection',
                    label='OpenBao Connection',
                    category='runtime',
                    status='success' if available else 'failed',
                    detail='Local connection observed.' if available else 'Connection unavailable or local mode disabled.',
                ),
            ),
            snapshot=CapabilitySnapshot(
                profile='openbao.local-connection.v1',
                compatibility_profile=None,
                capabilities=('health',) if available else (),
                observed_at=row.last_validated_at or identity.last_checked_at or now,
                metadata={'version': row.detected_version, 'ownership': row.ownership},
            ),
            message=identity.last_error or 'Independent credential authority and provider qualification remain pending.',
        )


runtime_adapter = OpenBaoRuntimeAdapter()
