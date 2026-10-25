"""KAORI Integration Kernel descriptor for GitHub App (SC-02 #2741).

Descriptors are intentionally inert. Do not wire into _load_builtins or
advertise GitHub as available before provider-specific UAT and admission.
"""

from __future__ import annotations

from datetime import UTC, datetime

from flask import url_for
from flask_login import current_user

from app.integrations.kernel.registry import (
    IntegrationImplementation,
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.adapter import runtime_adapter
from app.integrations.source_control.uat_access import local_super_admin
from app.models.source_control import SourceInstallation


def _detail_url(record: SourceInstallation, _section: str) -> str:
    """Route admitted UAT operators to this installation, never another scope."""
    if local_super_admin(current_user):
        return url_for('github_source_uat.detail', installation_id=record.id)
    # Keep ordinary Integration readers on the authorized read-side overview.
    # The installation detail remains protected by require_uat_access().
    return url_for('github_source.index')


def _record_failure(record: SourceInstallation, _error: Exception) -> None:
    """Store only safe operational status, never raw HTTP/body/credential."""
    canonical = record.integration_instance
    canonical.readiness_status = 'blocked'
    canonical.health_status = 'unhealthy'
    canonical.last_checked_at = datetime.now(UTC)
    canonical.last_error = 'GitHub App provider operation failed; review installation access.'


integration_module = IntegrationModule(
    integration_type='source_control',
    label='Source Control',
    domain_key='source_control',
    capability_key='source_control',
    icon='git-branch',
    description='Provider-neutral repository connectivity, provenance and delivery evidence.',
    workspace_endpoint='github_source.index',
    module_path='app.integrations.source_control.source_control.providers.github',
    worker_queue='integration-runtime',
    worker_domain='source-control-provider',
    operations=frozenset({
        'connection.test', 'runtime.validate', 'runtime.health', 'runtime.state',
    }),
    operation_queues={
        'connection.test': 'inline',
        'runtime.validate': 'integration-validation',
        'runtime.health': 'integration-runtime',
        'runtime.state': 'inline',
    },
    capability_keys=(
        'repository_inventory', 'source_revision', 'pull_requests',
        'workflow_runs', 'check_runs', 'deployments',
    ),
    compatibility_profiles=('github-app-readiness-v1',),
    runtime_label='Source Control',
    navigation_endpoint_prefixes=(
        'integrations.source_control', 'github_source.', 'github_source_uat.',
    ),
)

provider_implementation = IntegrationImplementation(
    integration_type='source_control',
    provider_key='github',
    adapter_key='github_rest_v3',
    adapter=runtime_adapter,
    instance_loader=model_loader(SourceInstallation),
    canonical_record_loader=canonical_model_loader(SourceInstallation),
    record_model=SourceInstallation,
    module_path='app.integrations.source_control.source_control.providers.github',
    detail_url_builder=_detail_url,
    failure_recorder=_record_failure,
)


def register_after_admission() -> bool:
    """Explicit future opt-in: blocked by the canonical provider lifecycle.

    The current Integration Kernel does NOT call this function. Only an
    approved workstream may wire it to the builtin loader after provider
    registration, security validation, webhook admission and UAT.
    """
    definition = provider_kind('source_control', 'github')
    if not definition.available:
        return False
    registry.register(integration_module)
    registry.register_implementation(provider_implementation)
    return True
