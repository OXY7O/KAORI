"""Fail-closed Kubespray preflight projection from committed KAORI evidence (#4800).

This is a non-mutating Plan/readiness view, never an executable playbook
or an approval token. Source-check evidence is not runtime admission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.integrations.orchestration.configuration_automation.providers.ansible.service import (
    source_validation_posture,
)
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution

_EVIDENCE_FRESHNESS = timedelta(minutes=15)
_HOST_PREFLIGHT_OPERATION = 'automation_kubespray_host_preflight'
_HOST_PREFLIGHT_RESULT_TYPE = 'automation_kubespray_host_preflight_v1'
_APPROVED_SCOPE = 'self_managed_existing_linux_hosts'
_NONPRODUCTION = frozenset(
    {'development', 'staging', 'testing', 'laboratory', 'sandbox', 'proof_of_concept', 'non_production'}
)


@dataclass(frozen=True, slots=True)
class KubesprayGate:
    key: str
    title: str
    state: str
    reason: str


@dataclass(frozen=True, slots=True)
class KubesprayPreflight:
    """Presentation-only status; no host/inventory or credentials are accepted from HTTP."""

    state: str
    verified_gates: int
    required_gates: int
    facts_job_public_id: str | None
    source_revision: str
    gates: tuple[KubesprayGate, ...]

    def presentation(self) -> dict[str, Any]:
        return {
            **asdict(self),
            'gates': [asdict(gate) for gate in self.gates],
        }


def _committed_host_evidence(
    connection: IntegrationInstance,
    jobs: list[JobExecution],
    *,
    now: datetime,
) -> tuple[dict[str, Any], str | None]:
    """Use only a recent, worker-owned canonical result tied to this connection.

    The current #4799 localhost job is intentionally excluded. Future remote
    host discovery must implement this specific attested result contract.
    """
    for job in jobs:
        if (
            job.integration_instance_id != connection.id
            or job.integration_type != 'configuration_automation'
            or job.job_type != 'infrastructure_automation'
            or job.operation != _HOST_PREFLIGHT_OPERATION
            or job.result_type != _HOST_PREFLIGHT_RESULT_TYPE
            or job.status != 'succeeded'
            or job.completed_at is None
        ):
            continue
        observed = job.completed_at
        if observed.tzinfo is None:
            # A naive timestamp is not a trustworthy time-bound attestation.
            continue
        if observed > now or now - observed > _EVIDENCE_FRESHNESS:
            continue
        facts = job.result_summary_json
        if not isinstance(facts, dict):
            continue
        meta = connection.metadata_json if isinstance(connection.metadata_json, dict) else {}
        if (
            facts.get('repository') != meta.get('source_repository')
            or facts.get('source_sha') != meta.get('source_sha')
            or facts.get('scope') != _APPROVED_SCOPE
            or facts.get('attestation') != 'verified_by_automation_worker'
        ):
            continue
        return facts, job.public_id
    return {}, None


def build_kubespray_preflight(
    connection: IntegrationInstance,
    *,
    jobs: list[JobExecution] | None = None,
    now: datetime | None = None,
) -> KubesprayPreflight:
    """Never infer provisionability from source, manual data or a cluster binding."""
    checked_at = now or datetime.now(UTC)
    metadata = connection.metadata_json if isinstance(connection.metadata_json, dict) else {}
    posture = source_validation_posture(connection)
    facts, facts_job_id = _committed_host_evidence(connection, jobs or [], now=checked_at)
    verified_facts = facts_job_id is not None

    gates = (
        KubesprayGate(
            'git_source',
            'Immutable Git Source',
            'ready' if posture['source_checked'] else 'blocked',
            'Reviewed Git commit and version policy are verified.'
            if posture['source_checked']
            else 'Revalidate the exact approved Git source and profile.',
        ),
        KubesprayGate(
            'target_classification',
            'Self-managed Target Scope',
            'ready'
            if verified_facts and connection.environment in _NONPRODUCTION and facts.get('target_class') == _APPROVED_SCOPE
            else 'blocked',
            'Only existing, non-production self-managed Linux hosts may be qualified.',
        ),
        KubesprayGate(
            'source_and_ee_admission',
            'Executable Source & EE Attestation',
            'ready' if verified_facts and facts.get('image_provenance_verified') is True else 'blocked',
            'Source registration and an optional digest do not prove worker image provenance.',
        ),
        KubesprayGate(
            'host_identity',
            'Trusted Host & Privilege',
            'ready'
            if verified_facts
            and facts.get('host_keys_verified') is True
            and facts.get('credential_reference_verified') is True
            and facts.get('privileged_identity_verified') is True
            else 'blocked',
            'Require trusted SSH host keys, approved credential references and privileged identity.',
        ),
        KubesprayGate(
            'host_facts',
            'OS & Capacity Evidence',
            'ready'
            if verified_facts and facts.get('os_support_verified') is True and facts.get('capacity_verified') is True
            else 'blocked',
            'Host OS, kernel, CPU, RAM, disk and package manager require observed worker facts.',
        ),
        KubesprayGate(
            'network',
            'CIDR & Network Reachability',
            'ready' if verified_facts and facts.get('network_verified') is True else 'blocked',
            'Pod/Service and existing CIDRs, interfaces, required ports and reachability need evidence.',
        ),
        KubesprayGate(
            'dns_clock',
            'DNS & Clock',
            'ready'
            if verified_facts and facts.get('dns_verified') is True and facts.get('time_sync_verified') is True
            else 'blocked',
            'DNS resolution and synchronized node time are unverified.',
        ),
        KubesprayGate(
            'cluster_topology',
            'Topology, Quorum & CRI/CNI',
            'ready'
            if verified_facts
            and facts.get('etcd_quorum_verified') is True
            and facts.get('control_plane_endpoint_verified') is True
            and facts.get('cri_cni_compatibility_verified') is True
            else 'blocked',
            'Control plane/etcd quorum, API endpoint and supported CRI/CNI are not proven.',
        ),
        KubesprayGate(
            'execution_scope',
            'Worker & Operation Admission',
            'ready'
            if verified_facts
            and facts.get('worker_execution_admitted') is True
            and facts.get('exact_inventory_verified') is True
            else 'blocked',
            'The local-only read-only Ansible pilot cannot authorize remote Kubespray operations.',
        ),
        KubesprayGate(
            'approval',
            'Plan, Approval & Change Window',
            'ready'
            if verified_facts
            and facts.get('plan_fingerprint_verified') is True
            and facts.get('maker_checker_approval_verified') is True
            and facts.get('maintenance_window_verified') is True
            else 'blocked',
            'An immutable Plan, independent approval and active change window are required.',
        ),
    )
    ready_count = sum(gate.state == 'ready' for gate in gates)
    return KubesprayPreflight(
        state='ready_for_review' if ready_count == len(gates) else 'blocked',
        verified_gates=ready_count,
        required_gates=len(gates),
        facts_job_public_id=facts_job_id,
        source_revision=str(metadata.get('source_sha') or ''),
        gates=gates,
    )
