"""Historical remote review posture from the latest canonical JobExecution (#5186).

No provider request, credential or trust hydration, task dispatch or authorization.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.infrastructure_automation.kubernetes.source_policy import SOURCE_CANDIDATE_SHA, committed_source_state
from app.infrastructure_automation.remote_job_review import REVIEW_OPERATION, REVIEW_RESULT_TYPE
from app.infrastructure_automation.remote_preflight_source import REMOTE_CANDIDATE_SHA
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.fingerprint import payload_fingerprint

_HEX = re.compile(r'[a-f0-9]{64}')
_EE = re.compile(r'sha256:[a-f0-9]{64}')
_PARAMETER_KEYS = frozenset({
    'schema_version', 'actor_id', 'connection_id', 'profile_sha', 'remote_candidate_sha',
    'ee_digest', 'inventory_fingerprint', 'host_registry_fingerprint',
    'target_review_fingerprint', 'execution_authorized',
})
_NEGATIVE_FLAGS = frozenset({
    'execution_authorized', 'runtime_attestation_verified', 'full_preflight_verified',
    'credential_material_accessed', 'ssh_executed', 'mutation_authorized',
})
_RESULT_KEYS = _PARAMETER_KEYS | _NEGATIVE_FLAGS | {
    'source_review_fingerprint', 'worker_review_fingerprint', 'expires_at', 'status',
}


@dataclass(frozen=True, slots=True)
class RemoteReviewPosture:
    state: str
    label: str
    tone: str
    description: str
    execution_authorized: bool = False

    def presentation(self) -> dict[str, Any]:
        return asdict(self)


def _unqualified() -> RemoteReviewPosture:
    return RemoteReviewPosture(
        'unqualified', 'Review Unqualified', 'blocked', 'The latest review evidence requires requalification.'
    )


def _matches_job(connection: IntegrationInstance, job: JobExecution) -> bool:
    return (
        connection.integration_type == 'configuration_automation'
        and connection.provider_key == 'ansible'
        and job.integration_instance_id == connection.id
        and job.integration_type == connection.integration_type
        and job.job_type == 'infrastructure_automation'
        and job.operation == REVIEW_OPERATION
        and job.queue_name == 'automation'
        and job.workload_class == 'validation'
        and job.scope_type == 'ansible_source_connection'
        and job.scope_key == str(connection.id)
        and job.resource_group == f'kubespray:remote-preflight-review:{connection.id}'
        and type(job.requested_by_user_id) is int
        and job.requested_by_user_id > 0
        and job.max_attempts == 1
    )


def _matches_receipt(job: JobExecution, receipt: dict[str, Any]) -> bool:
    payload = job.payload_json
    if not isinstance(payload, dict) or set(receipt) != _RESULT_KEYS:
        return False
    parameters = {key: value for key, value in payload.items() if key != '_progress'}
    return (
        set(parameters) == _PARAMETER_KEYS
        and payload_fingerprint(parameters) == job.parameter_fingerprint
        and payload_fingerprint({key: receipt[key] for key in _PARAMETER_KEYS}) == job.parameter_fingerprint
        and type(receipt['schema_version']) is int
        and receipt['schema_version'] == 1
        and type(receipt['actor_id']) is int
        and receipt['actor_id'] == job.requested_by_user_id
        and type(receipt['connection_id']) is int
        and receipt['connection_id'] == job.integration_instance_id
        and receipt['profile_sha'] == SOURCE_CANDIDATE_SHA
        and receipt['remote_candidate_sha'] == REMOTE_CANDIDATE_SHA
        and isinstance(receipt['ee_digest'], str)
        and _EE.fullmatch(receipt['ee_digest']) is not None
        and receipt['status'] == 'review_evidence_recorded'
        and all(receipt[key] is False for key in _NEGATIVE_FLAGS)
        and all(
            isinstance(receipt[key], str) and _HEX.fullmatch(receipt[key]) is not None
            for key in (
                'inventory_fingerprint', 'host_registry_fingerprint', 'target_review_fingerprint',
                'source_review_fingerprint', 'worker_review_fingerprint',
            )
        )
    )


def _qualified_expiry(job: JobExecution, receipt: dict[str, Any], now: datetime) -> datetime | None:
    completed = job.completed_at
    expiry = receipt.get('expires_at')
    if (
        not isinstance(completed, datetime)
        or completed.utcoffset() is None
        or now.utcoffset() is None
        or completed > now
        or not isinstance(expiry, str)
    ):
        return None
    try:
        expires_at = datetime.fromisoformat(expiry)
    except ValueError:
        return None
    return expires_at if expires_at.utcoffset() is not None and completed < expires_at else None


def review_remote_job_posture(
    connection: IntegrationInstance, job: JobExecution | None, *, now: datetime
) -> RemoteReviewPosture:
    """Never treat a historical review receipt as current execution authority."""
    if job is None:
        return RemoteReviewPosture(
            'not_recorded', 'Not Recorded', 'unknown', 'No remote review receipt has been recorded for this connection.'
        )
    if not _matches_job(connection, job):
        return _unqualified()
    if job.status in ('queued', 'running', 'retrying', 'cancel_requested'):
        return RemoteReviewPosture(
            'pending', 'Review Pending', 'pending', 'The latest review attempt has not committed a completed receipt.'
        )
    if job.status != 'succeeded':
        return RemoteReviewPosture(
            'blocked', 'Review Blocked', 'blocked', 'The latest review attempt did not succeed; older receipts are not reused.'
        )
    receipt = job.result_summary_json
    if (
        job.result_type != REVIEW_RESULT_TYPE
        or job.attempt_count != 1
        or not isinstance(receipt, dict)
        or not _matches_receipt(job, receipt)
    ):
        return _unqualified()
    expires_at = _qualified_expiry(job, receipt, now)
    if expires_at is None:
        return _unqualified()
    metadata = connection.metadata_json
    if (
        not connection.enabled
        or not isinstance(metadata, dict)
        or committed_source_state(metadata) != 'checked'
        or metadata.get('source_sha') != receipt['profile_sha']
        or metadata.get('execution_environment_digest') != receipt['ee_digest']
    ):
        return RemoteReviewPosture(
            'source_changed', 'Source Changed', 'blocked', 'The committed source or execution environment must be requalified.'
        )
    if now >= expires_at:
        return RemoteReviewPosture(
            'expired', 'Review Expired', 'blocked', 'The recorded review validity has ended; a new review is required.'
        )
    return RemoteReviewPosture(
        'historical', 'Historical Review', 'attention',
        'A review receipt was recorded. Current access, native runtime, SSH and full preflight are not verified here.',
    )


def committed_remote_review_posture(connection: IntegrationInstance) -> RemoteReviewPosture:
    """Use the newest attempt, irrespective of success or failure."""
    job = JobExecution.query.filter_by(
        integration_type='configuration_automation',
        integration_instance_id=connection.id,
        operation=REVIEW_OPERATION,
    ).order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).first()
    return review_remote_job_posture(connection, job, now=datetime.now(UTC))
