"""Source Control repository inventory worker using canonical JobExecution (#2742).

Only installed, individually admitted GitHub installations are processed.
Canonical Jobs owns retries, cancellation, status, progress and audit. No
credentials, token or raw provider response is present in task arguments.
"""

from __future__ import annotations

from typing import cast

from billiard.exceptions import SoftTimeLimitExceeded
from celery import shared_task
from sqlalchemy.orm import Session

from app.extensions.db import db
from app.integrations.source_control.source_control.providers.github.repository_sync import (
    synchronize_installation,
)
from app.integrations.source_control.eligibility import MAX_INSTALLATIONS, _eligible
from app.models.source_control import SourceInstallation
from app.platform_operations.jobs.execution import JobCancellationRequested, JobExecutionContext


@shared_task(
    bind=True,
    name='app.integrations.source_control.tasks.sync_source_repositories',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_source_repositories_task(
    self,
    *,
    targets: list[dict[str, int]],
    requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, int | str]:
    context = JobExecutionContext(str(self.request.id), job_execution_id)
    total = len(targets)
    if (
        not 1 <= total <= MAX_INSTALLATIONS
        or any(
            not isinstance(item, dict)
            or set(item) != {'installation_id'}
            or isinstance(item['installation_id'], bool)
            or not isinstance(item['installation_id'], int)
            or item['installation_id'] <= 0
            for item in targets
        )
        or len({item['installation_id'] for item in targets}) != total
    ):
        context.fail('Source Control inventory target scope is invalid.', error_code='invalid_scope')
        return {'status': 'failed', 'synced_installations': 0, 'failed_installations': total}

    context.start(
        message='Preparing approved GitHub installation grants.',
        total=total,
        percent=1,
        stage='Preparing Inventory',
        target='Source Control',
    )
    successes = 0
    failures = 0
    repositories = 0
    revisions = 0
    revision_gaps = 0
    try:
        for index, target in enumerate(targets, start=1):
            context.checkpoint(
                current=index - 1,
                total=total,
                percent=min(5 + 85 * (index - 1) // total, 90),
                stage='Collecting Repository Metadata',
                target='GitHub Installation',
            )
            try:
                installation = db.session.get(SourceInstallation, target['installation_id'])
                if installation is None or not _eligible(installation):
                    raise ValueError('Source Control installation is no longer eligible.')
                result = synchronize_installation(cast(Session, db.session), installation)
                successes += 1
                repositories += int(result.observed_count or 0)
                revisions += int(result.committed_revisions)
                revision_gaps += int(result.revision_failures + result.unchecked_revisions)
            except JobCancellationRequested:
                db.session.rollback()
                raise
            except SoftTimeLimitExceeded:
                db.session.rollback()
                context.fail(
                    'Source Control inventory exceeded its worker time limit; committed scope retained.',
                    error_code='source_control_inventory_timeout',
                )
                return {
                    'status': 'failed',
                    'synced_installations': successes,
                    'failed_installations': failures + 1,
                }
            except Exception:
                # Never serialize provider errors, URLs, PEMs, tokens or raw
                # payloads into JobExecution, logs, or Notifications.
                db.session.rollback()
                failures += 1
            context.checkpoint(
                current=index,
                total=total,
                percent=min(5 + 90 * index // total, 95),
                stage='Committing Repository Scope',
                target='Source Control',
            )
        result = {
            'status': (
                'failed' if failures and not successes else 'partial' if failures or revision_gaps else 'success'
            ),
            'synced_installations': successes,
            'failed_installations': failures,
            'observed_repositories': repositories,
            'observed_default_branch_shas': revisions,
            'revision_evidence_gaps': revision_gaps,
        }
        if failures and not successes:
            context.fail(
                'No GitHub installation scan completed; prior committed evidence was retained.',
                error_code='source_control_inventory_failed',
            )
        else:
            context.succeed(
                result_summary=result,
                result_type='source_control_repository_inventory',
                partial=bool(failures or revision_gaps),
            )
        return result
    except JobCancellationRequested:
        context.canceled()
        return {
            'status': 'canceled',
            'synced_installations': successes,
            'failed_installations': failures,
        }
