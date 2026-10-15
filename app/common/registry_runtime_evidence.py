"""Committed Registry-to-Kubernetes correlation readiness for cross-domain consumers.

Only KAORI-persisted JobExecution and inventory generations are read here.
Registry owns materialization; Intelligence consumes this neutral evidence status.
There are no live provider requests or orchestration side effects.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy.orm import Session

from app.models.integration import IntegrationInstance
from app.models.inventory import ClusterInventory
from app.models.job import JobExecution
from app.models.registry import RegistryCollectionState


def _active_registry_source_ids(session: Session) -> list[int]:
    return [
        int(source_id)
        for (source_id,) in session.query(IntegrationInstance.id)
        .filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.lifecycle_status == 'active',
            IntegrationInstance.enabled.is_(True),
        )
        .all()
    ]


def runtime_input_signature(session: Session) -> str:
    """Fingerprint committed Registry and Kubernetes generation authorities.

    No provider calls and no full artifact or Pod inventory traversal.
    """
    source_ids = _active_registry_source_ids(session)
    registry_rows = (
        session.query(
            RegistryCollectionState.integration_instance_id,
            RegistryCollectionState.last_committed_at,
        )
        .filter(RegistryCollectionState.integration_instance_id.in_(source_ids))
        .all()
    )
    pod_generations = session.query(ClusterInventory.cluster_id, ClusterInventory.collected_at).all()
    evidence = {
        'active_registry_sources': sorted(source_ids),
        'registry': sorted(
            (int(source_id), committed_at.isoformat() if committed_at else None)
            for source_id, committed_at in registry_rows
        ),
        'kubernetes': sorted(
            (str(cluster_id), collected_at.isoformat() if collected_at else None)
            for cluster_id, collected_at in pod_generations
        ),
    }
    return sha256(json.dumps(evidence, sort_keys=True).encode('utf-8')).hexdigest()


def runtime_correlation_evidence_readiness(
    session: Session,
    *,
    signature_fn: Callable[[Session], str] | None = None,
) -> dict[str, str]:
    """Qualify committed runtime evidence without live provider I/O."""
    jobs = session.query(JobExecution).filter(JobExecution.job_type == 'artifact_registry_runtime_correlation')
    latest = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).first()
    successful = (
        jobs.filter(JobExecution.status.in_(('succeeded', 'partially_succeeded')))
        .order_by(JobExecution.completed_at.desc(), JobExecution.id.desc())
        .first()
    )

    if successful is None:
        return {
            'status': 'not_materialized',
            'title': 'Runtime Correlation Required',
            'description': (
                'No successful committed Registry-to-Kubernetes correlation exists. '
                'Run the registered Runtime Correlation job before interpreting absent findings.'
            ),
        }

    summary = successful.result_summary_json if isinstance(successful.result_summary_json, dict) else {}
    committed_signature = summary.get('input_signature')
    if not committed_signature or committed_signature != (signature_fn or runtime_input_signature)(session):
        return {
            'status': 'inputs_changed',
            'title': 'Runtime Correlation Inputs Changed',
            'description': (
                'Committed Registry or Kubernetes inventory changed after the last correlation. '
                'Stored scan vulnerabilities are not remediated merely because runtime findings disappear. '
                'Refresh Runtime Correlation to requalify exposure.'
            ),
        }

    if latest is not None and latest.is_active:
        return {
            'status': 'refreshing',
            'title': 'Runtime Correlation Refreshing',
            'description': 'A registered correlation job is in progress; the prior committed snapshot remains provisional.',
        }
    if latest is not None and latest.status == 'failed' and latest.created_at > successful.created_at:
        return {
            'status': 'refresh_failed',
            'title': 'Runtime Correlation Refresh Failed',
            'description': 'The latest refresh failed; review Job Executions before treating an absent binding as resolved.',
        }
    observed_at = successful.completed_at or successful.created_at
    if observed_at is None or observed_at < datetime.now(UTC) - timedelta(hours=24):
        return {
            'status': 'stale',
            'title': 'Runtime Correlation Evidence Stale',
            'description': 'The last successful correlation is over 24 hours old. Refresh before relying on runtime exposure.',
        }
    return {
        'status': 'ready',
        'title': 'Runtime Correlation Ready',
        'description': 'Current committed Registry and Kubernetes input generations match the last successful correlation.',
    }
