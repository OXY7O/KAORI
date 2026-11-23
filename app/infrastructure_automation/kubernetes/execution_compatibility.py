"""Source-defined Kubespray lifecycle compatibility, distinct from API support (#5156).

This is a pure, committed-evidence qualification for REVIEW, not an
execution capability, approval, SSH preflight or Kubernetes API probe.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.definitions.loader import load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str, unique_by
from app.infrastructure_automation.kubernetes.committed_preflight import KubesprayPreflight
from app.infrastructure_automation.kubernetes.kubespray_preflight import KUBESPRAY_KUBERNETES_MINOR
from app.infrastructure_automation.kubernetes.source_policy import (
    PROFILE_KEY,
    committed_source_state,
)
from app.integrations.compatibility import COMPATIBILITY_LIFECYCLE_POLICY, kubernetes_lifecycle
from app.models.integration import IntegrationInstance

_DEFINITION = 'automation/kubespray_execution_compatibility.yaml'
_EE_DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')
_TARGET_MINOR = re.compile(r'1\.\d{1,2}\Z')


@dataclass(frozen=True, slots=True)
class KubesprayOperationQualification:
    operation: str
    label: str
    state: str
    reason: str
    execution_authorized: bool = False

    def presentation(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class KubesprayExecutionCompatibility:
    profile_key: str
    policy_key: str
    policy_window: str
    target_minor: str
    api_support_posture: str
    operations: tuple[KubesprayOperationQualification, ...]
    execution_authorized: bool = False

    def presentation(self) -> dict[str, Any]:
        return {
            **asdict(self),
            'operations': [item.presentation() for item in self.operations],
        }


def _operations() -> tuple[tuple[str, str, str], ...]:
    """Reject malformed/duplicate source policy, never grant an ad-hoc operation."""
    document = load_definition_document(_DEFINITION, expected_kind='kubespray_execution_compatibility')
    if require_str(document, 'profile_key', _DEFINITION) != PROFILE_KEY:
        raise ValueError('Kubespray profile definition is not the admitted source contract.')
    if require_str(document, 'support_policy', _DEFINITION) != COMPATIBILITY_LIFECYCLE_POLICY.key:
        raise ValueError('Kubespray policy must reference the current KAORI lifecycle authority.')
    items = [
        require_mapping(item, f'operations[{index}]')
        for index, item in enumerate(require_list(document.get('operations'), 'operations'))
    ]
    unique_by(items, 'key', 'operations')
    operations: list[tuple[str, str, str]] = []
    for index, item in enumerate(items):
        path = f'operations[{index}]'
        key = require_str(item, 'key', path)
        label = require_str(item, 'label', path)
        posture = require_str(item, 'posture', path)
        if posture not in {'review_only', 'not_admitted'}:
            raise ValueError('Unknown Kubespray operation posture cannot grant execution.')
        operations.append((key, label, posture))
    if not operations or not any(key == 'plan_review' and posture == 'review_only' for key, _, posture in operations):
        raise ValueError('Kubespray review-only operation definition is missing.')
    return tuple(operations)


def assess_kubespray_execution_compatibility(
    connection: IntegrationInstance,
    preflight: KubesprayPreflight,
    *,
    target_minor: str | None = None,
) -> KubesprayExecutionCompatibility:
    """Assess only trusted KAORI state. Never return mutation authority.

    The target minor is an explicitly frozen *candidate*, not a detected
    Kubernetes API server version. The preflight remains independently
    responsible for checking real worker-observed host and topology facts.
    """
    version = target_minor if target_minor is not None else KUBESPRAY_KUBERNETES_MINOR
    minor = version if isinstance(version, str) and _TARGET_MINOR.fullmatch(version) else 'unknown'
    api_state = kubernetes_lifecycle(minor) if minor != 'unknown' else 'unknown'
    metadata = connection.metadata_json if type(connection.metadata_json) is dict else {}
    exact_source = (
        connection.integration_type == 'configuration_automation'
        and connection.provider_key == 'ansible'
        and metadata.get('profile_key') == PROFILE_KEY
        and committed_source_state(metadata) == 'checked'
    )
    digest = metadata.get('execution_environment_digest')
    verified_ee_reference = isinstance(digest, str) and _EE_DIGEST.fullmatch(digest) is not None
    review_qualified = (
        exact_source
        and verified_ee_reference
        and minor == KUBESPRAY_KUBERNETES_MINOR
        and api_state == 'current'
        and preflight.state == 'ready_for_review'
        and preflight.facts_job_public_id is not None
        and preflight.gates[2].state == 'ready'
    )
    if minor == 'unknown':
        reason = 'Target Kubernetes minor is unknown or malformed.'
    elif api_state != 'current':
        reason = 'Kubernetes API lifecycle support does not qualify this target for Kubespray lifecycle changes.'
    elif minor != KUBESPRAY_KUBERNETES_MINOR:
        reason = 'The target minor is outside the exact reviewed Kubespray pilot version.'
    elif not exact_source:
        reason = 'Approved immutable Git source and Ansible toolchain evidence are missing or mismatched.'
    elif not verified_ee_reference:
        reason = 'An immutable Execution Environment sha256 digest reference is required.'
    elif not review_qualified:
        reason = 'Trusted current host, topology and Execution Environment preflight is required.'
    else:
        reason = 'Pinned source and preflight qualify review only; independent approval and execution remain blocked.'
    operations = tuple(
        KubesprayOperationQualification(
            operation=key,
            label=label,
            state='qualified_for_review' if posture == 'review_only' and review_qualified else 'blocked',
            reason=reason
            if posture == 'review_only'
            else 'This operation has no independently admitted Run authority.',
        )
        for key, label, posture in _operations()
    )
    return KubesprayExecutionCompatibility(
        profile_key=PROFILE_KEY,
        policy_key=COMPATIBILITY_LIFECYCLE_POLICY.key,
        policy_window=COMPATIBILITY_LIFECYCLE_POLICY.window_label,
        target_minor=minor,
        api_support_posture=api_state,
        operations=operations,
    )
