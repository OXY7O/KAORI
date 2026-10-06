from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter, time
from typing import Any

from celery import chord, shared_task

from app.artifact_registry.security.queue import get_registry_security_queue_name
from app.artifact_registry.security.sync import sync_registry_security
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.execution import JobExecutionContext
from app.platform_operations.jobs.serialization import to_json_compatible
from app.platform_operations.notifications.service import create_notification

logger = logging.getLogger(__name__)

_PROGRESS_SOURCE_KEY = 'registry_security_sources'
_PROGRESS_COMPLETED_SOURCE_KEY = 'registry_security_completed_sources'


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class _SecuritySourceProgress:
    source_key: str
    source_total: int
    instance_name: str
    item_current: int
    item_total: int
    item_name: str
    stage: str
    message: str
    completed: bool = False


def _checkpoint_source_progress(
    *,
    job_execution_id: int | None,
    event: _SecuritySourceProgress,
) -> None:
    """Update one fleet Job Execution from an independently running Registry source."""

    if job_execution_id is None:
        return

    job = JobExecution.query.filter(JobExecution.id == job_execution_id).with_for_update().first()
    if job is None or job.is_terminal:
        db.session.rollback()
        return

    payload = dict(job.payload_json or {})
    progress = dict(payload.get('_progress') or {})
    source_progress = dict(progress.get(_PROGRESS_SOURCE_KEY) or {})

    local_fraction = event.item_current / max(event.item_total, 1) if event.item_total else 0.0
    previous_fraction = float(source_progress.get(event.source_key) or 0.0)
    source_progress[event.source_key] = max(previous_fraction, min(max(local_fraction, 0.0), 1.0))

    aggregate_fraction = sum(float(value or 0.0) for value in source_progress.values()) / max(event.source_total, 1)
    aggregate_percent = min(5 + int(aggregate_fraction * 88), 93)
    current_percent = int(progress.get('percent') or 0)

    completed_sources = {str(value) for value in (progress.get(_PROGRESS_COMPLETED_SOURCE_KEY) or []) if str(value)}
    if event.completed:
        completed_sources.add(event.source_key)
        source_progress[event.source_key] = 1.0
        aggregate_fraction = sum(float(value or 0.0) for value in source_progress.values()) / max(event.source_total, 1)
        aggregate_percent = min(5 + int(aggregate_fraction * 88), 93)

    progress[_PROGRESS_SOURCE_KEY] = source_progress
    progress[_PROGRESS_COMPLETED_SOURCE_KEY] = sorted(completed_sources)
    progress['percent'] = max(current_percent, aggregate_percent)
    progress['stage'] = event.stage[:120]
    progress['target'] = (
        f'{event.instance_name} · {event.item_name}' if event.item_name else event.instance_name
    )[:255]
    progress['updated_at'] = _now_iso()

    payload['_progress'] = progress
    job.payload_json = to_json_compatible(payload)
    job.progress_current = len(completed_sources)
    job.progress_total = max(event.source_total, 0)
    job.progress_message = event.message[:255]
    job.heartbeat_at = datetime.now(UTC)
    db.session.commit()


def _source_result_base(target: dict[str, str]) -> dict[str, Any]:
    return {
        'integration_instance_id': str(target.get('integration_instance_id') or ''),
        'instance_name': str(target.get('instance_name') or ''),
        'provider_key': str(target.get('provider_key') or ''),
        'artifact_count': 0,
        'refreshed_report_count': 0,
        'reused_report_count': 0,
        'finding_count': 0,
        'repository_failure_count': 0,
        'failure_evidence': [],
        'warning_evidence': [],
    }


@shared_task(
    bind=True,
    name='app.artifact_registry.security.tasks.sync_registry_security_source',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_registry_security_source_task(
    self,
    *,
    target: dict[str, str],
    source_total: int,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    result = _source_result_base(target)
    instance_name = result['instance_name']
    canonical_id = int(result['integration_instance_id'])
    source_key = result['integration_instance_id']

    _checkpoint_source_progress(
        job_execution_id=job_execution_id,
        event=_SecuritySourceProgress(
            source_key=source_key,
            source_total=source_total,
            instance_name=instance_name,
            item_current=0,
            item_total=0,
            item_name='',
            stage='Preparing Registry Security Source',
            message=f'Preparing incremental security refresh for {instance_name}.',
        ),
    )

    def report_security_progress(item_current: int, item_total: int, item_name: str) -> None:
        stage = 'Discovering Registry Security' if item_total == 0 else 'Collecting Registry Security'
        message = (
            f'Processed security evidence for {item_current} of {item_total} artifacts.'
            if item_total
            else f'Discovering security evidence for {instance_name}.'
        )
        _checkpoint_source_progress(
            job_execution_id=job_execution_id,
            event=_SecuritySourceProgress(
                source_key=source_key,
                source_total=source_total,
                instance_name=instance_name,
                item_current=item_current,
                item_total=item_total,
                item_name=item_name,
                stage=stage,
                message=message,
            ),
        )
        self.update_state(
            state='PROGRESS',
            meta={
                'job_execution_id': job_execution_id,
                'integration_instance_id': source_key,
                'instance_name': instance_name,
                'item_processed_count': item_current,
                'item_total_count': item_total,
                'current_item_name': item_name,
                'progress_stage': stage,
                'message': message,
                'heartbeat_at': _now_iso(),
            },
        )

    try:
        identity = db.session.get(IntegrationInstance, canonical_id)
        if identity is None:
            raise LookupError('The Registry integration was deleted after the security job was admitted.')

        collected = sync_registry_security(
            identity,
            progress_callback=report_security_progress,
        )
        result['artifact_count'] = int(collected.get('artifacts') or 0)
        result['refreshed_report_count'] = int(collected.get('refreshed_reports') or 0)
        result['reused_report_count'] = int(collected.get('reused_reports') or 0)
        result['finding_count'] = int(collected.get('findings') or 0)

        provider_metadata = (
            dict(collected.get('provider_metadata') or {})
            if isinstance(collected.get('provider_metadata'), dict)
            else {}
        )
        repository_failures = list(provider_metadata.get('repository_failures') or [])
        repository_failure_count = int(provider_metadata.get('repository_failure_count') or len(repository_failures))
        result['repository_failure_count'] = repository_failure_count

        warning_evidence: list[dict[str, str]] = []
        for failure in repository_failures:
            if not isinstance(failure, dict):
                continue
            warning_evidence.append(
                {
                    'integration_instance_id': source_key,
                    'instance_name': instance_name,
                    'provider_key': result['provider_key'],
                    'project_name': str(failure.get('project_name') or ''),
                    'repository_name': str(failure.get('repository_name') or ''),
                    'error_type': str(failure.get('error_type') or 'RepositoryRefreshUnavailable'),
                    'message': str(failure.get('message') or '')[:500],
                }
            )
        result['warning_evidence'] = warning_evidence[:50]
        result['status'] = 'warning' if repository_failure_count else 'success'
    except Exception as exc:
        db.session.rollback()
        result['status'] = 'error'
        result['failure_evidence'] = [
            {
                'integration_instance_id': source_key,
                'instance_name': instance_name,
                'provider_key': result['provider_key'],
                'error_type': type(exc).__name__,
                'message': str(exc),
            }
        ]
        logger.exception('Artifact Registry security synchronization failed for %s.', instance_name)

    result['duration_seconds'] = round(perf_counter() - started, 1)
    result['finished_at'] = _now_iso()
    completed_message = (
        f'Finished security collection for {instance_name}.'
        if result['status'] != 'error'
        else f'Security collection failed for {instance_name}; previous committed evidence remains available.'
    )
    _checkpoint_source_progress(
        job_execution_id=job_execution_id,
        event=_SecuritySourceProgress(
            source_key=source_key,
            source_total=source_total,
            instance_name=instance_name,
            item_current=1,
            item_total=1,
            item_name='',
            stage='Registry Security Source Completed',
            message=completed_message,
            completed=True,
        ),
    )
    return result


@shared_task(
    bind=True,
    name='app.artifact_registry.security.tasks.finalize_registry_security_sync',
    acks_late=True,
    reject_on_worker_lost=True,
)
def finalize_registry_security_sync_task(
    self,
    source_results: list[dict[str, Any]],
    *,
    requested_by_user_id: int | None,
    source_total: int,
    started_at_epoch: float,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    context = JobExecutionContext(task_id, job_execution_id)

    try:
        normalized_results = [item for item in source_results if isinstance(item, dict)]
        failures = [
            failure
            for item in normalized_results
            for failure in list(item.get('failure_evidence') or [])
            if isinstance(failure, dict)
        ]
        warning_evidence = [
            warning
            for item in normalized_results
            for warning in list(item.get('warning_evidence') or [])
            if isinstance(warning, dict)
        ]
        synced = sum(1 for item in normalized_results if str(item.get('status') or '') != 'error')
        partial_source_count = sum(1 for item in normalized_results if str(item.get('status') or '') == 'warning')
        repository_failure_count = sum(int(item.get('repository_failure_count') or 0) for item in normalized_results)
        artifact_count = sum(int(item.get('artifact_count') or 0) for item in normalized_results)
        refreshed_reports = sum(int(item.get('refreshed_report_count') or 0) for item in normalized_results)
        reused_reports = sum(int(item.get('reused_report_count') or 0) for item in normalized_results)
        finding_count = sum(int(item.get('finding_count') or 0) for item in normalized_results)

        has_partial_refresh = bool(partial_source_count or repository_failure_count)
        status = 'error' if failures and not synced else ('warning' if failures or has_partial_refresh else 'success')
        result = {
            'status': status,
            'title': (
                'Artifact Registry Security Sync Completed'
                if status != 'error'
                else 'Artifact Registry Security Sync Failed'
            ),
            'message': (
                f'{synced} Registry provider(s) synchronized; {len(failures)} failed; '
                f'{repository_failure_count} repository refresh warning(s).'
            ),
            'detail': (
                'Failed providers retained their previous committed security evidence.'
                if failures and not synced
                else (
                    'Security evidence was committed for available repositories; previous committed evidence '
                    'was retained for repositories that could not be refreshed.'
                    if has_partial_refresh
                    else (
                        f'{artifact_count} artifacts evaluated; {refreshed_reports} vulnerability report(s) refreshed '
                        f'and {reused_reports} unchanged report(s) reused.'
                    )
                )
            ),
            'total_count': source_total,
            'synced_count': synced,
            'failed_count': len(failures),
            'artifact_count': artifact_count,
            'refreshed_report_count': refreshed_reports,
            'reused_report_count': reused_reports,
            'finding_count': finding_count,
            'partial_source_count': partial_source_count,
            'repository_failure_count': repository_failure_count,
            'failure_evidence': failures,
            'warning_evidence': warning_evidence[:50],
            'requested_by_user_id': requested_by_user_id,
            'finished_at': _now_iso(),
            'duration_seconds': round(max(time() - float(started_at_epoch), 0.0), 1),
        }

        context.checkpoint(
            current=source_total,
            total=source_total,
            percent=98,
            stage='Finalizing Registry Security',
            target='Registry Estate',
            message='Finalizing committed Artifact Registry security evidence.',
        )

        canonical_task_id = task_id
        if job_execution_id is not None:
            job = db.session.get(JobExecution, job_execution_id)
            if job is not None and job.celery_task_id:
                canonical_task_id = str(job.celery_task_id)

        if requested_by_user_id is not None:
            create_notification(
                user_id=requested_by_user_id,
                event_type='artifact_registry_security_sync',
                status=status,
                title=result['title'],
                message=result['message'],
                detail=result['detail'],
                action_url='/artifact-registry/security',
                metadata={'task_id': canonical_task_id, 'job_execution_id': job_execution_id, **result},
            )

        if failures and not synced:
            context.fail(
                'All eligible Registry providers failed security synchronization.',
                error_code='artifact_registry_security_sync_failed',
            )
        else:
            context.succeed(
                result_summary=result,
                result_type='artifact_registry_security_sync',
                partial=bool(failures or has_partial_refresh),
            )
        return result
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='artifact_registry_security_sync_failed')
        logger.exception('Unexpected Artifact Registry security finalization failure.')
        raise


@shared_task(
    bind=True,
    name='app.artifact_registry.security.tasks.sync_all_registry_security',
    acks_late=False,
    reject_on_worker_lost=False,
)
def sync_all_registry_security_task(
    self,
    *,
    requested_by_user_id: int | None,
    targets: list[dict[str, str]] | None = None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    context = JobExecutionContext(task_id, job_execution_id)
    targets = list(targets or [])
    total = len(targets)

    context.start(
        message='Preparing Artifact Registry security synchronization.',
        total=total,
        percent=1,
        stage='Preparing Registry Security',
        target='Registry Estate',
    )

    try:
        if job_execution_id is None:
            raise RuntimeError('Artifact Registry Security Sync requires a canonical Job Execution.')
        if not targets:
            raise RuntimeError('Artifact Registry Security Sync has no eligible Registry source.')

        queue_name = get_registry_security_queue_name()
        context.checkpoint(
            current=0,
            total=total,
            percent=5,
            stage='Dispatching Registry Security Sources',
            target='Registry Estate',
            message=f'Dispatching {total} Registry source(s) to the dedicated security queue.',
        )

        header = [
            sync_registry_security_source_task.s(
                target=target,
                source_total=total,
                job_execution_id=job_execution_id,
            ).set(queue=queue_name)
            for target in targets
        ]
        callback = finalize_registry_security_sync_task.s(
            requested_by_user_id=requested_by_user_id,
            source_total=total,
            started_at_epoch=time(),
            job_execution_id=job_execution_id,
        ).set(queue=queue_name)

        chord(header, callback).apply_async()
        return {
            'status': 'dispatched',
            'total_count': total,
            'queue_name': queue_name,
            'job_execution_id': job_execution_id,
            'dispatched_at': _now_iso(),
        }
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='artifact_registry_security_sync_dispatch_failed')
        logger.exception('Could not dispatch Artifact Registry security source work.')
        raise
