"""Canonical manual-only Jobs producer for Vault Alert Source observations.

Alertmanager owns retrieval. KAORI writes only opaque committed correlation
handles; no secret-bearing source data enters JobExecution or Celery messages.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime

from app.common.job_execution_presentation import present_job_execution
from app.extensions.db import db
from app.integrations.observability.alert_source.providers.alertmanager.client_factory import build_client
from app.intelligence.alert_signals.vault_source import (
    _validated_binding,
    commit_vault_alert_observations,
    fail_vault_alert_observations,
)
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES, WORKLOAD_STANDARD
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job
from app.platform_operations.jobs.execution import JobCancellationRequested, JobExecutionContext

JOB_KEY = 'secrets_pki.vault_alerts.observe'
OPERATION = 'observe_vault_alert_source'
JOB_TYPE = 'secrets_pki_vault_alert_observation'
_MAX_VAULT_SOURCES = 25
_HMAC_HEX = re.compile(r'[0-9a-fA-F]{64,128}\Z')


class NoEligibleVaultAlertSources(ValueError):
    """Only generic source admission details are safe for operator messages."""


def _provider_for(binding: IntegrationBinding) -> AlertmanagerInstance | None:
    provider = AlertmanagerInstance.query.filter_by(
        integration_instance_id=binding.integration_instance_id,
    ).first()
    if (
        provider is None
        or not provider.enabled
        or not provider.endpoint
        or provider.readiness_status not in {'ready', 'degraded'}
    ):
        return None
    return provider


def build_vault_alert_observation_targets(*, now: datetime | None = None) -> list[int]:
    """Bound the fleet and select only unambiguous committed Alert Source bindings."""
    instant = now or datetime.now(UTC)
    vault_ids = (
        db.session.query(IntegrationInstance.id)
        .filter(
            IntegrationInstance.integration_type == 'secrets_pki',
            IntegrationInstance.provider_key == 'vault',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(IntegrationInstance.id.asc())
        .limit(_MAX_VAULT_SOURCES + 1)
        .all()
    )
    if len(vault_ids) > _MAX_VAULT_SOURCES:
        raise NoEligibleVaultAlertSources('Vault Alert Source fleet exceeds bounded collection capacity.')
    targets: list[int] = []
    for (vault_id,) in vault_ids:
        rows = (
            IntegrationBinding.query.filter_by(
                asset_type='vault_instance',
                asset_key=str(vault_id),
                enabled=True,
            )
            .join(
                IntegrationInstance,
                IntegrationInstance.id == IntegrationBinding.integration_instance_id,
            )
            .filter(
                IntegrationInstance.integration_type == 'alert_source',
                IntegrationInstance.enabled.is_(True),
                IntegrationInstance.lifecycle_status == 'active',
            )
            .limit(2)
            .all()
        )
        if len(rows) != 1:
            continue
        binding = rows[0]
        if _validated_binding(binding.id, now=instant) is None:
            continue
        if _provider_for(binding) is not None:
            targets.append(binding.id)
    return targets


def dispatch_vault_alert_observations(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict | None = None,
) -> RegisteredJobDispatchResult:
    """Manual operator UAT only; no policy/Beat scheduling is admitted."""
    if trigger_type != 'manual':
        return RegisteredJobDispatchResult(
            status='blocked',
            message='Vault alert observation is manual-only.',
        )
    try:
        targets = build_vault_alert_observation_targets()
    except NoEligibleVaultAlertSources as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    if not targets:
        return RegisteredJobDispatchResult(
            status='blocked',
            message='No qualified Vault Alert Source is eligible.',
        )
    from app.intelligence.alert_signals.tasks import observe_vault_alert_source

    job, created = enqueue_canonical_job(
        task=observe_vault_alert_source,
        task_kwargs={'binding_ids': targets},
        job_type=JOB_TYPE,
        operation=OPERATION,
        queue_name='inventory',
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='secrets_pki',
        scope_type='secrets_pki_alert_fleet',
        scope_key='all',
        resource_group='secrets-pki-vault-alerts:global',
        parameters={'scope': 'qualified_vault_alert_sources', 'target_count': len(targets)},
        payload={'target_count': len(targets), 'trigger_type': 'manual'},
        max_attempts=1,
        dispatch_options=JobDispatchOptions(
            require_registered_worker=True,
            soft_time_limit_seconds=240,
            hard_time_limit_seconds=300,
        ),
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message='Vault alert evidence collection queued.' if created else 'Joined the active observation.',
        job=job,
        created=created,
    )


def build_vault_alert_job_context(policy: JobPolicy) -> dict:
    try:
        targets = build_vault_alert_observation_targets()
        diagnostics = []
    except NoEligibleVaultAlertSources:
        targets = []
        diagnostics = ['Vault source fleet exceeds the bounded observation profile.']
    jobs = JobExecution.query.filter_by(job_type=JOB_TYPE, operation=OPERATION)
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    active = (
        jobs.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    registered = IntegrationInstance.query.filter_by(
        integration_type='secrets_pki',
        provider_key='vault',
    ).count()
    count = len(targets)
    return {
        'registered_system_count': registered,
        'eligible_system_count': count,
        'eligible_target_count': count,
        'blocked_system_count': max(registered - count, 0),
        'diagnostics': diagnostics,
        'interval_label': 'Manual Only',
        'latest_job': present_job_execution(recent[0]) if recent else None,
        'recent_jobs': [present_job_execution(row) for row in recent],
        'active_job': present_job_execution(active) if active else None,
        'execution_state': {
            'label': 'Execution Active' if active else ('Ready' if count else 'Blocked'),
            'tone': 'pending' if active else ('normal' if count else 'warning'),
            'icon': 'loader-circle' if active else ('circle-check' if count else 'shield-alert'),
            'description': (
                'Manual source-qualified Alertmanager observation.'
                if count
                else 'Validate a Vault Alert Source binding before manual execution.'
            ),
        },
        'configuration_state': {
            'label': 'Manual Only',
            'tone': 'unknown',
            'icon': 'hand',
        },
        'scheduler_state': {
            'label': 'Unsupported',
            'tone': 'disabled',
            'icon': 'circle-pause',
            'description': 'Automatic observation is not admitted.',
        },
        'readiness_state': {
            'label': 'Source Eligible' if count else 'Blocked',
            'tone': 'normal' if count else 'warning',
            'icon': 'link-2' if count else 'shield-alert',
            'description': 'Only validated canonical Vault Alertmanager sources.',
        },
    }


def _worker_key() -> bytes | None:
    """Read a stable independent secret at the worker boundary, never from jobs."""
    secret = os.getenv('KAORI_VAULT_ALERT_CORRELATION_HMAC_KEY_HEX', '')
    if not _HMAC_HEX.fullmatch(secret):
        return None
    return bytes.fromhex(secret)


def observe_vault_alert_binding(binding_id: int, *, key: bytes) -> str:
    """Fetch a single filtered provider source; redact every possible exception."""
    now = datetime.now(UTC)
    eligible = _validated_binding(binding_id, now=now)
    if eligible is None:
        return 'blocked'
    binding, _source = eligible
    provider = _provider_for(binding)
    if provider is None:
        return 'blocked'
    try:
        client = build_client(provider)
        response = client.get_alerts(filters=[f'vault_instance="{binding.asset_key}"'])
        observed = datetime.now(UTC)
        result = commit_vault_alert_observations(
            binding_id=binding.id,
            alerts=response,
            hmac_key=key,
            observed_at=observed,
            now=observed,
        )
        return result['state']
    except Exception:
        # Alertmanager/transport errors may include credentials, paths and URLs.
        # Never include the exception in JobExecution, logs or committed evidence.
        db.session.rollback()
        try:
            fail_vault_alert_observations(binding_id=binding_id, observed_at=datetime.now(UTC))
        except Exception:
            db.session.rollback()
        return 'unavailable'


def run_vault_alert_observation_job(
    *,
    task_id: str,
    job_execution_id: int | None,
    binding_ids: list[int],
) -> dict[str, int | str]:
    """Execute only the canonical manual JobExecution with current source admission."""
    if type(job_execution_id) is not int or not task_id:
        return {'status': 'blocked', 'observed_sources': 0, 'failed_sources': 0}
    job = db.session.get(JobExecution, job_execution_id)
    if (
        job is None
        or job.celery_task_id != task_id
        or job.job_type != JOB_TYPE
        or job.operation != OPERATION
        or job.scope_type != 'secrets_pki_alert_fleet'
        or job.scope_key != 'all'
        or job.status not in {'queued', 'retrying'}
        or job.integration_type != 'secrets_pki'
        or job.requested_by_user_id is None
        or not isinstance(job.payload_json, dict)
        or job.payload_json.get('trigger_type') != 'manual'
    ):
        return {'status': 'blocked', 'observed_sources': 0, 'failed_sources': 0}
    ctx = JobExecutionContext(task_id, job_execution_id)
    try:
        current_targets = build_vault_alert_observation_targets()
    except Exception:
        # Do not surface source/database exception details through JobExecution.
        db.session.rollback()
        current_targets = []
    if (
        not isinstance(binding_ids, list)
        or not 1 <= len(binding_ids) <= _MAX_VAULT_SOURCES
        or any(type(item) is not int or item < 1 for item in binding_ids)
        or len(set(binding_ids)) != len(binding_ids)
        or binding_ids != current_targets
    ):
        ctx.fail('Vault Alert Source target admission changed.', error_code='invalid_source_scope')
        failed_count = len(binding_ids) if isinstance(binding_ids, list) else 0
        return {'status': 'failed', 'observed_sources': 0, 'failed_sources': failed_count}
    key = _worker_key()
    if key is None:
        ctx.fail('Vault alert correlation secret is unavailable.', error_code='correlation_key_unavailable')
        return {'status': 'failed', 'observed_sources': 0, 'failed_sources': len(binding_ids)}
    observed = 0
    failed = 0
    unobserved = 0
    ctx.start(
        message='Preparing qualified Vault Alert Sources.',
        total=len(binding_ids),
        stage='Source Validation',
        target='Secrets & PKI',
    )
    try:
        for index, binding_id in enumerate(binding_ids, start=1):
            ctx.checkpoint(
                current=index - 1,
                total=len(binding_ids),
                stage='Observing Alertmanager',
                target='Approved Vault Source',
            )
            outcome = observe_vault_alert_binding(binding_id, key=key)
            if outcome in {'qualified', 'unobserved'}:
                observed += 1
                unobserved += int(outcome == 'unobserved')
            else:
                failed += 1
            ctx.checkpoint(
                current=index,
                total=len(binding_ids),
                stage='Evidence Commitment',
                target='Secrets & PKI',
            )
        result = {
            'status': 'failed' if failed == len(binding_ids) else ('partial' if failed else 'success'),
            'observed_sources': observed,
            'unobserved_sources': unobserved,
            'failed_sources': failed,
        }
        if failed == len(binding_ids):
            ctx.fail('All Vault Alert Source observations were unavailable.', error_code='source_unavailable')
        else:
            ctx.succeed(
                result_summary=result,
                result_type='secrets_pki_alert_observation',
                partial=bool(failed),
            )
        return result
    except JobCancellationRequested:
        ctx.canceled()
        return {
            'status': 'canceled',
            'observed_sources': observed,
            'failed_sources': failed,
        }
