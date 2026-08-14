from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SystemRunbookDefinition:
    """Source-controlled KAORI runbook contract exposed through System Runbook Catalog."""

    runbook_key: str
    title: str
    description: str
    domain: str
    asset_kind: str
    version: str
    action_key: str
    resolver_key: str
    approval_policy: str
    maturity: str
    validation_status: str
    verification_summary: str
    recovery_summary: str
    required_evidence: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    compatibility_profiles: tuple[str, ...]
    change_level: str
    parameter_schema: dict[str, Any]
    steps: tuple[dict[str, Any], ...]
    recovery: dict[str, Any] | None
    default_evidence_mapping: dict[str, str]

    def revision_payload(self) -> dict[str, Any]:
        return {
            'runbook_key': self.runbook_key,
            'version': self.version,
            'action_key': self.action_key,
            'resolver_key': self.resolver_key,
            'approval_policy': self.approval_policy,
            'required_evidence': sorted(self.required_evidence),
            'required_capabilities': sorted(self.required_capabilities),
            'compatibility_profiles': sorted(self.compatibility_profiles),
            'change_level': self.change_level,
            'parameter_schema': dict(self.parameter_schema),
            'steps': [dict(step) for step in self.steps],
            'rollback': dict(self.recovery) if self.recovery else None,
        }

    @property
    def content_hash(self) -> str:
        encoded = json.dumps(
            self.revision_payload(),
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
        ).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()


SYSTEM_RUNBOOK_CATALOG: tuple[SystemRunbookDefinition, ...] = (
    SystemRunbookDefinition(
        runbook_key='kubernetes.deployment.restart',
        title='Restart Kubernetes Deployment',
        description=(
            'Controlled Kubernetes Deployment restart using the KAORI resolver, immutable authorization, '
            'server-side dry-run, and post-action rollout verification.'
        ),
        domain='kubernetes',
        asset_kind='deployment',
        version='1.0.0',
        action_key='kubernetes.deployment.restart',
        resolver_key='kubernetes.deployment.restart',
        approval_policy='needs_approval',
        maturity='validated',
        validation_status='system_tested',
        verification_summary=(
            'KAORI waits for observed generation and desired replicas to converge before marking remediation verified.'
        ),
        recovery_summary=(
            'Restart is not transactionally reversible. KAORI records a manual compensating-recovery snapshot and '
            'escalates verification failure.'
        ),
        required_evidence=('deployment_name',),
        required_capabilities=('kubernetes.deployments.patch',),
        compatibility_profiles=('kubernetes-v1',),
        change_level='major',
        parameter_schema={
            'type': 'object',
            'properties': {
                'deployment_name': {'type': 'string'},
                'resource_version': {'type': 'string'},
            },
            'required': ['deployment_name'],
            'additionalProperties': False,
        },
        steps=(
            {
                'type': 'resolver_action',
                'action': 'kubernetes.deployment.restart',
            },
        ),
        recovery={
            'mode': 'manual_compensating_recovery',
            'owner': 'platform-operations',
            'escalate_on_verification_failure': True,
        },
        default_evidence_mapping={'deployment_name': 'deployment'},
    ),
)


SYSTEM_RUNBOOK_KEYS = frozenset(item.runbook_key for item in SYSTEM_RUNBOOK_CATALOG)


def list_system_runbooks() -> tuple[SystemRunbookDefinition, ...]:
    return SYSTEM_RUNBOOK_CATALOG


def get_system_runbook(runbook_key: str) -> SystemRunbookDefinition | None:
    normalized = str(runbook_key or '').strip()
    return next((item for item in SYSTEM_RUNBOOK_CATALOG if item.runbook_key == normalized), None)


def is_system_runbook_key(runbook_key: str) -> bool:
    return str(runbook_key or '').strip() in SYSTEM_RUNBOOK_KEYS
