"""Canonical Jobs admission for Source Control repository reconciliation (#2742).

Uses Jobs registry / resource slots / existing inventory worker. Does not
mutate provider, reveal credentials in kwargs or create a second scheduler.
"""

from __future__ import annotations

from flask import current_app

from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.uat_access import local_super_admin, uat_enabled
from app.extensions.db import db
from app.models.user import User
from app.models.source_control import SourceInstallation
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job

JOB_KEY = 'source_control.repository.sync'
OPERATION = 'sync_source_control_repositories'
MAX_INSTALLATIONS = 25


class NoEligibleSourceControlTargets(RuntimeError):
    """There are no admitted and validated GitHub App installation grants."""


def _eligible(installation: SourceInstallation) -> bool:
    identity = installation.integration_instance
    app = installation.github_app_credential
    account = installation.account
    return bool(
        identity is not None
        and identity.id == installation.integration_instance_id
        and identity.integration_type == 'source_control'
        and identity.provider_key == 'github'
        and identity.adapter_key == 'github_rest_v3'
        and identity.enabled
        and identity.lifecycle_status == 'active'
        and identity.readiness_status == 'ready'
        and installation.provider_key == 'github'
        and installation.host_key == 'github.com'
        and installation.repository_scope in {'all', 'selected'}
        and account is not None
        and account.provider_key == 'github'
        and account.host_key == installation.host_key
        and installation.account_id == account.id
        and app is not None
        and app.enabled
        and app.host_key == installation.host_key
        and app.native_app_id == installation.native_app_id
        and installation.github_app_credential_id == app.id
    )


def build_source_repository_targets(
    *, installation_record_id: int | None = None,
) -> list[dict[str, int]]:
    """Fail closed for provider not admitted, excessive scope or stale grants."""
    if not provider_kind('source_control', 'github').available:
        raise NoEligibleSourceControlTargets('GitHub provider admission is pending.')
    if installation_record_id is not None:
        if (
            isinstance(installation_record_id, bool)
            or not isinstance(installation_record_id, int)
            or installation_record_id <= 0
        ):
            raise NoEligibleSourceControlTargets('Source Control installation scope is invalid.')
        installation = SourceInstallation.query.filter_by(id=installation_record_id).first()
        if installation is None or not _eligible(installation):
            raise NoEligibleSourceControlTargets('Selected installation is not validated or authorized.')
        return [{'installation_id': int(installation.id)}]

    rows = SourceInstallation.query.order_by(SourceInstallation.id).limit(MAX_INSTALLATIONS + 1).all()
    if len(rows) > MAX_INSTALLATIONS:
        raise NoEligibleSourceControlTargets(
            'Source Control installations exceed the bounded reconciliation limit.'
        )
    return [{'installation_id': int(row.id)} for row in rows if _eligible(row)]


def enqueue_source_repository_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    installation_record_id: int | None = None,
):
    from app.integrations.source_control.tasks import sync_source_repositories_task

    if trigger_type == 'manual':
        raise NoEligibleSourceControlTargets(
            'Manual Source Control job dispatch requires resource-scoped admission (#724).'
        )
    if trigger_type == 'uat':
        if not uat_enabled() or requested_by_user_id is None:
            raise NoEligibleSourceControlTargets('Explicit Source Control UAT admission is required.')
        actor = db.session.get(User, requested_by_user_id)
        if not local_super_admin(actor) or installation_record_id is None:
            raise NoEligibleSourceControlTargets('UAT refresh requires a scoped local administrator.')
    if trigger_type not in {'scheduled', 'on_demand', 'recovery', 'uat'}:
        raise ValueError('Unsupported Source Control inventory trigger.')
    if trigger_type in {'on_demand', 'recovery'} and requested_by_user_id is not None:
        raise NoEligibleSourceControlTargets(
            'Provider-triggered refresh does not accept an end-user actor bypass.'
        )
    targets = build_source_repository_targets(installation_record_id=installation_record_id)
    if not targets:
        raise NoEligibleSourceControlTargets(
            'No admitted, Ready GitHub App installation is eligible for inventory.'
        )
    scoped_id = installation_record_id if installation_record_id is not None else None
    scope = f'installation:{scoped_id}' if scoped_id is not None else 'all'
    return enqueue_canonical_job(
        task=sync_source_repositories_task,
        task_kwargs={'targets': targets, 'requested_by_user_id': requested_by_user_id},
        job_type='source_control_repository_inventory',
        operation=OPERATION,
        queue_name='inventory',
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='source_control',
        scope_type='source_control_installation' if scoped_id is not None else 'source_control_installation_fleet',
        scope_key=scope,
        resource_group=f'source-control-repository-sync:{scope}',
        parameters={'target_count': len(targets), 'scope': scope},
        payload={'target_count': len(targets), 'trigger_type': trigger_type},
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=1740,
            hard_time_limit_seconds=1800,
        ),
    )
