"""Admission-gated bridge to KAORI's existing integration JobExecution path.

SC-02 #2741. Do not add a second Celery task, queue, job store, lock or
provider scheduler for GitHub. Normal validation/web helpers already create
durable JobExecution and use integration-validation/integration-runtime.
"""

from __future__ import annotations

from typing import Any, Literal

from app.integrations.kernel.registry import get_integration
from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.integrations.validation.web import enqueue_instance_validation, enqueue_runtime_health_refresh
from app.models.source_control import SourceInstallation

_JobOperation = Literal['full_validation', 'runtime_refresh']


def _require_admitted_installation(installation: SourceInstallation) -> int:
    if not provider_kind('source_control', 'github').available:
        raise GitHubProviderError('GitHub App job admission is pending.')
    canonical = installation.integration_instance
    credential = installation.github_app_credential
    if (
        canonical is None
        or canonical.integration_type != 'source_control'
        or canonical.provider_key != 'github'
        or canonical.adapter_key != 'github_rest_v3'
        or not canonical.enabled
        or canonical.lifecycle_status != 'active'
        or installation.integration_instance_id != canonical.id
        or installation.provider_key != 'github'
        or installation.host_key != 'github.com'
        or installation.account is None
        or credential is None
        or installation.github_app_credential_id != credential.id
        or not credential.enabled
        or credential.host_key != installation.host_key
        or credential.native_app_id != installation.native_app_id
    ):
        raise GitHubProviderError('GitHub App connection is not eligible for worker admission.')

    # Normal worker dispatch must resolve the same registered implementation
    # that the worker will use. Fail before producing any JobExecution if not
    # yet loaded/admitted in the shared Integration Kernel.
    module = get_integration('source_control')
    instance = module.require_record_for_canonical(canonical.id)
    if instance.id != installation.id:
        raise GitHubProviderError('GitHub App implementation record identity does not match.')
    if module.implementation_for_record(instance).provider_key != 'github':
        raise GitHubProviderError('GitHub App implementation is not registered.')
    return int(canonical.id)


def enqueue_github_app_job(
    installation: SourceInstallation, *,
    operation: _JobOperation,
    requested_by_user_id: int,
) -> tuple[dict[str, Any], bool]:
    """Delegate to canonical JobExecution without transmitting any credential."""
    if operation not in ('full_validation', 'runtime_refresh'):
        raise ValueError('Unsupported GitHub App integration job.')
    if isinstance(requested_by_user_id, bool) or requested_by_user_id <= 0:
        raise ValueError('An authenticated KAORI actor is required.')
    identity = _require_admitted_installation(installation)
    kwargs = {
        'integration_type': 'source_control',
        'integration_instance_id': identity,
        'requested_by_user_id': requested_by_user_id,
    }
    if operation == 'full_validation':
        return enqueue_instance_validation(**kwargs)
    return enqueue_runtime_health_refresh(**kwargs)
