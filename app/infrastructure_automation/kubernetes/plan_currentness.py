"""Canonical read-only Kubespray Plan freshness projection (#4800).

A successful Plan JobExecution commits a *review artifact*, not an approval.
Always rederive the whole Plan from the latest host evidence; do not
resurrect an older successful Plan after a failed or superseding attempt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.infrastructure_automation.kubernetes.plan_review import (
    PLAN_OPERATION,
    PLAN_RESULT_TYPE,
    build_kubespray_plan_review,
)
from app.integrations.orchestration.configuration_automation.providers.ansible.preflight import (
    KubesprayPreflight,
    committed_kubespray_preflight,
)
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution


@dataclass(frozen=True, slots=True)
class KubesprayPlanCurrentness:
    """Non-authorizing, committed-evidence status safe for a detail workspace."""

    state: str
    description: str
    job_public_id: str | None = None
    plan_fingerprint: str | None = None
    expires_at: str | None = None
    execution_authorized: bool = False

    def presentation(self) -> dict[str, Any]:
        return asdict(self)


def _is_qualified_plan_job(connection: IntegrationInstance, latest_plan_job: JobExecution, timestamp: datetime) -> bool:
    """Validate the latest immutable job envelope before comparing plan evidence."""
    return (
        latest_plan_job.integration_instance_id == connection.id
        and latest_plan_job.integration_type == 'configuration_automation'
        and latest_plan_job.job_type == 'infrastructure_automation'
        and latest_plan_job.operation == PLAN_OPERATION
        and latest_plan_job.queue_name == 'automation'
        and latest_plan_job.result_type == PLAN_RESULT_TYPE
        and latest_plan_job.status == 'succeeded'
        and latest_plan_job.completed_at is not None
        and latest_plan_job.completed_at.tzinfo is not None
        and latest_plan_job.completed_at <= timestamp
    )


def evaluate_kubespray_plan_currentness(
    connection: IntegrationInstance,
    *,
    latest_plan_job: JobExecution | None,
    latest_host_preflight: KubesprayPreflight,
    host_preflight_job: JobExecution | None,
    now: datetime | None = None,
) -> KubesprayPlanCurrentness:
    """Recompute the current Plan, rejecting drift or any newer failed attempt.

    The caller must provide the newest *attempt*, not the newest successful
    attempt, and the current canonical host-preflight projection.
    """
    timestamp = now or datetime.now(UTC)
    blocked = KubesprayPlanCurrentness(
        'blocked',
        'No approved Kubespray Plan exists. Execution remains blocked.',
    )
    if timestamp.tzinfo is None:
        return blocked
    if latest_plan_job is None:
        return KubesprayPlanCurrentness(
            'not_generated',
            'No committed review-only Plan has been generated.',
        )
    if not _is_qualified_plan_job(connection, latest_plan_job, timestamp):
        return blocked
    summary = latest_plan_job.result_summary_json
    if not isinstance(summary, dict):
        return blocked
    if (
        summary.get('mutation_authorized') is not False
        or summary.get('approval_status') != 'not_requested'
        or summary.get('execution_status') != 'blocked'
    ):
        return blocked

    expiry_value = summary.get('expires_at')
    if not isinstance(expiry_value, str):
        return blocked
    try:
        expiry = datetime.fromisoformat(expiry_value)
    except ValueError:
        return blocked
    if expiry.tzinfo is None or expiry <= latest_plan_job.completed_at:
        return blocked
    if timestamp >= expiry:
        return KubesprayPlanCurrentness(
            'expired',
            'The last review-only Plan has expired. Refresh trusted preflight evidence.',
        )

    if (
        latest_host_preflight.state != 'ready_for_review'
        or not latest_host_preflight.facts_job_public_id
        or host_preflight_job is None
        or host_preflight_job.integration_instance_id != connection.id
        or host_preflight_job.public_id != latest_host_preflight.facts_job_public_id
    ):
        return blocked

    rebuilt = build_kubespray_plan_review(connection, host_preflight_job, now=timestamp)
    if (
        rebuilt.status != 'requires_independent_approval'
        or not rebuilt.plan_fingerprint
        or summary != rebuilt.committed_summary()
    ):
        return blocked
    return KubesprayPlanCurrentness(
        'current_for_review',
        'Plan evidence is current for independent review only; no Run approval exists.',
        job_public_id=latest_plan_job.public_id,
        plan_fingerprint=rebuilt.plan_fingerprint,
        expires_at=rebuilt.expires_at,
    )


def committed_kubespray_plan_currentness(
    connection: IntegrationInstance,
    *,
    preflight: KubesprayPreflight | None = None,
) -> KubesprayPlanCurrentness:
    """Use committed JobExecution state exclusively, with bounded indexed reads."""
    latest = (
        JobExecution.query.filter_by(
            integration_instance_id=connection.id,
            operation=PLAN_OPERATION,
        )
        .order_by(JobExecution.created_at.desc(), JobExecution.id.desc())
        .first()
    )
    current_preflight = preflight if preflight is not None else committed_kubespray_preflight(connection)
    host = (
        JobExecution.query.filter_by(
            integration_instance_id=connection.id,
            public_id=current_preflight.facts_job_public_id,
        ).first()
        if current_preflight.facts_job_public_id
        else None
    )
    return evaluate_kubespray_plan_currentness(
        connection,
        latest_plan_job=latest,
        latest_host_preflight=current_preflight,
        host_preflight_job=host,
    )
