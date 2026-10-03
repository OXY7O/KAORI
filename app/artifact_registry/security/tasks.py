from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.artifact_registry.security.sync import sync_registry_security
from app.models.integration import IntegrationInstance
from app.platform_operations.jobs.execution import JobExecutionContext


@shared_task(
    bind=True,
    name='app.artifact_registry.security.tasks.sync_artifact_registry_security',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_artifact_registry_security_task(
    self,
    *,
    requested_by_user_id: int | None,
    targets: list[dict[str, str]],
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    context = JobExecutionContext(str(self.request.id), job_execution_id)
    started = perf_counter()
    total = len(targets)
    synced = 0
    findings = critical = high = signatures = sboms = 0
    failures: list[dict[str, str]] = []
    context.start(
        message='Preparing Artifact Registry security evidence synchronization.',
        total=total,
        percent=1,
        stage='Preparing Registry Security',
        target='Registry Estate',
    )
    for index, target in enumerate(targets, start=1):
        instance = IntegrationInstance.query.get(int(target['integration_instance_id']))
        if instance is None:
            failures.append({'instance': target['instance_name'], 'error': 'Registry integration no longer exists.'})
            continue
        context.checkpoint(
            current=index - 1,
            total=total,
            percent=min(5 + int(((index - 1) / max(total, 1)) * 90), 95),
            stage='Collecting Security Evidence',
            target=instance.name,
            message=f'Collecting scanner and supply-chain metadata from {instance.name}.',
        )
        try:
            result = sync_registry_security(instance)
        except Exception as exc:
            failures.append({'instance': instance.name, 'error': str(exc)})
            continue
        synced += 1
        findings += int(result['findings'])
        critical += int(result['critical'])
        high += int(result['high'])
        signatures += int(result['signatures'])
        sboms += int(result['sboms'])

    status = 'success' if not failures else ('warning' if synced else 'error')
    result = {
        'status': status,
        'requested_by_user_id': requested_by_user_id,
        'total_count': total,
        'synced_count': synced,
        'failed_count': len(failures),
        'finding_count': findings,
        'critical_count': critical,
        'high_count': high,
        'signature_observed_count': signatures,
        'sbom_observed_count': sboms,
        'failures': failures,
        'finished_at': datetime.now(UTC).isoformat(),
        'duration_seconds': round(perf_counter() - started, 1),
    }
    context.checkpoint(
        current=total,
        total=total,
        percent=98,
        stage='Finalizing Registry Security',
        target='Registry Estate',
        message='Finalizing committed Artifact Registry security evidence.',
    )
    if failures and not synced:
        context.fail(
            'All eligible Registry sources failed security evidence synchronization.',
            error_code='artifact_registry_security_failed',
        )
    else:
        context.succeed(
            result_summary=result,
            result_type='artifact_registry_security_sync',
            partial=bool(failures),
        )
    return result
