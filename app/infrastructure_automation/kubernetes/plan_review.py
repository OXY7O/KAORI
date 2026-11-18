"""Bounded immutable Kubespray Plan candidate from committed preflight (#4800).

A Plan candidate is review material, never an approval or executable dispatch
envelope. Only hashed asset/network identity is copied into its JobExecution.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.infrastructure_automation.kubernetes.committed_preflight import build_kubespray_preflight
from app.infrastructure_automation.kubernetes.kubespray_preflight import (
    KUBESPRAY_COMMIT,
    KUBESPRAY_KUBERNETES_MINOR,
    KUBESPRAY_RELEASE,
    assess_static_kubespray_pilot,
)
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution

PLAN_RESULT_TYPE = 'automation_kubespray_plan_review_v1'
PLAN_OPERATION = 'automation_kubespray_plan_review'
PLAN_FRESHNESS = timedelta(minutes=15)
_PLAN_VERSION = 1


@dataclass(frozen=True, slots=True)
class KubesprayPlanReview:
    """Sanitized review-only reference; this object cannot authorize execution."""

    status: str
    reason_code: str
    plan_fingerprint: str | None = None
    inventory_fingerprint: str | None = None
    host_preflight_job_public_id: str | None = None
    expires_at: str | None = None
    source_sha: str | None = None
    execution_environment_digest: str | None = None
    mutation_authorized: bool = False

    def committed_summary(self) -> dict[str, Any]:
        """Store no raw inventory, host names/IPs, SSH material or approval claims."""
        return {
            'schema_version': _PLAN_VERSION,
            'status': self.status,
            'reason_code': self.reason_code,
            'plan_fingerprint': self.plan_fingerprint,
            'inventory_fingerprint': self.inventory_fingerprint,
            'host_preflight_job_public_id': self.host_preflight_job_public_id,
            'expires_at': self.expires_at,
            'source_sha': self.source_sha,
            'execution_environment_digest': self.execution_environment_digest,
            'upstream_kubespray_commit': KUBESPRAY_COMMIT,
            'mutation_authorized': False,
            'approval_status': 'not_requested',
            'execution_status': 'blocked',
        }


def build_kubespray_plan_review(
    connection: IntegrationInstance,
    host_preflight_job: JobExecution,
    *,
    now: datetime | None = None,
) -> KubesprayPlanReview:
    """Derive a deterministic candidate, never trusting user-supplied run flags."""
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        return KubesprayPlanReview('blocked', 'CLOCK_UNQUALIFIED')
    if (
        connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or not connection.enabled
        or connection.lifecycle_status != 'active'
    ):
        return KubesprayPlanReview('blocked', 'CONNECTION_NOT_ADMITTED')
    metadata = connection.metadata_json if isinstance(connection.metadata_json, dict) else {}
    source_sha = metadata.get('source_sha')
    if not isinstance(source_sha, str) or len(source_sha) != 40:
        return KubesprayPlanReview('blocked', 'SOURCE_UNQUALIFIED')
    ee_digest = metadata.get('execution_environment_digest')
    if not isinstance(ee_digest, str) or re.fullmatch(r'sha256:[a-f0-9]{64}', ee_digest) is None:
        return KubesprayPlanReview('blocked', 'EE_DIGEST_REQUIRED')

    posture = build_kubespray_preflight(connection, jobs=[host_preflight_job], now=timestamp)
    if posture.state != 'ready_for_review' or posture.facts_job_public_id != host_preflight_job.public_id:
        return KubesprayPlanReview('blocked', 'HOST_PREFLIGHT_UNQUALIFIED')

    facts = host_preflight_job.result_summary_json
    if not isinstance(facts, dict):
        return KubesprayPlanReview('blocked', 'HOST_PREFLIGHT_UNQUALIFIED')
    if facts.get('execution_environment_digest') != ee_digest:
        return KubesprayPlanReview('blocked', 'EE_DIGEST_MISMATCH')
    nodes = facts.get('hosts')
    if not isinstance(nodes, list) or len(nodes) != 3:
        return KubesprayPlanReview('blocked', 'INVENTORY_UNQUALIFIED')

    # Source data is a committed worker observation; the target asset registry
    # and SSH identity still require independent admission before any Run.
    allowed_nodes = []
    required = (
        'asset_id',
        'role',
        'os_distribution',
        'os_release',
        'cpu_count',
        'memory_mib',
        'disk_gib',
        'address',
    )
    for node in nodes:
        if not isinstance(node, dict) or any(field not in node for field in required):
            return KubesprayPlanReview('blocked', 'INVENTORY_UNQUALIFIED')
        allowed_nodes.append(
            {
                'asset_id': node['asset_id'],
                'role': node['role'],
                'os_distribution': node['os_distribution'],
                'os_version': node['os_release'],
                'cpu_count': node['cpu_count'],
                'memory_mib': node['memory_mib'],
                'disk_gib': node['disk_gib'],
                'address': node['address'],
            }
        )

    environment = str(connection.environment or '').lower()
    if environment not in {
        'development',
        'testing',
        'staging',
        'laboratory',
        'sandbox',
        'proof_of_concept',
        'non_production',
    }:
        return KubesprayPlanReview('blocked', 'ENVIRONMENT_UNQUALIFIED')
    static = assess_static_kubespray_pilot(
        {
            'management': 'self_managed',
            'environment': 'development' if environment == 'development' else 'uat',
            'kubespray_release': facts.get('upstream_kubespray_release'),
            'kubespray_commit': facts.get('upstream_kubespray_commit'),
            'kubernetes_minor': facts.get('kubernetes_minor'),
            'pod_cidr': facts.get('pod_cidr'),
            'service_cidr': facts.get('service_cidr'),
            'nodes': allowed_nodes,
        }
    )
    if static.status != 'requires_provider_evidence' or not static.inventory_fingerprint:
        return KubesprayPlanReview('blocked', 'STATIC_TARGET_UNQUALIFIED')

    observed_at = host_preflight_job.completed_at
    if observed_at is None or observed_at.tzinfo is None:
        return KubesprayPlanReview('blocked', 'HOST_PREFLIGHT_EXPIRED')
    expiry = observed_at + PLAN_FRESHNESS
    if timestamp >= expiry:
        return KubesprayPlanReview('blocked', 'HOST_PREFLIGHT_EXPIRED')

    # A hash is a correlation fingerprint, NOT a cryptographic approval proof.
    fields = {
        'schema_version': _PLAN_VERSION,
        'connection_id': connection.id,
        'environment': environment,
        'repository': metadata.get('source_repository'),
        'source_sha': source_sha,
        'execution_environment_digest': ee_digest,
        'kubespray_release': KUBESPRAY_RELEASE,
        'upstream_commit': KUBESPRAY_COMMIT,
        'kubernetes_minor': KUBESPRAY_KUBERNETES_MINOR,
        'inventory_fingerprint': static.inventory_fingerprint,
        'host_preflight_job_public_id': host_preflight_job.public_id,
        'host_observed_at': observed_at.astimezone(UTC).isoformat(),
        'expires_at': expiry.astimezone(UTC).isoformat(),
    }
    fingerprint = hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    ).hexdigest()
    return KubesprayPlanReview(
        status='requires_independent_approval',
        reason_code='REVIEW_ONLY',
        plan_fingerprint=fingerprint,
        inventory_fingerprint=static.inventory_fingerprint,
        host_preflight_job_public_id=host_preflight_job.public_id,
        expires_at=fields['expires_at'],
        source_sha=source_sha,
        execution_environment_digest=ee_digest,
    )
