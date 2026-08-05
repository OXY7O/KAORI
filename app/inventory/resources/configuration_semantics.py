from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

COLLECTED = 'Collected'
NOT_REPORTED = 'Not Reported'
NOT_APPLICABLE = 'Not Applicable'
NOT_CONFIGURED = 'Not Configured'

CONFIGMAP_EVIDENCE_KEY = 'inventory.configmaps'
SECRET_EVIDENCE_KEY = 'inventory.secrets'
POD_EVIDENCE_KEY = 'inventory.pods'


def configuration_evidence_key(object_type: str | None) -> str:
    return SECRET_EVIDENCE_KEY if str(object_type or '').casefold() == 'secret' else CONFIGMAP_EVIDENCE_KEY


def collection_state(evidence: Mapping[str, Any] | None, evidence_key: str) -> str:
    return str((evidence or {}).get(evidence_key) or NOT_REPORTED)


def aggregate_collection_states(states: Iterable[str]) -> str:
    normalized = sorted({str(state or NOT_REPORTED) for state in states})
    if not normalized:
        return NOT_REPORTED
    if len(normalized) == 1:
        return normalized[0]
    return f"Mixed: {', '.join(normalized)}"


def secret_type_presentation(object_type: str | None, secret_type: str | None) -> str:
    if str(object_type or '').casefold() != 'secret':
        return NOT_APPLICABLE
    return str(secret_type or 'Opaque')


def mutation_presentation(immutable: bool) -> tuple[str, str]:
    return ('Immutable', 'info') if immutable else ('Mutable', 'brand')


def pod_reference_presentation(reference_count: int | None, pod_collection_state: str) -> dict[str, str]:
    if pod_collection_state != COLLECTED or reference_count is None:
        return {
            'label': NOT_REPORTED,
            'supporting': f'Pod collection: {pod_collection_state}',
            'tone': 'unknown',
        }
    if reference_count <= 0:
        return {
            'label': 'No Current References',
            'supporting': 'No reference in the committed Pod snapshot',
            'tone': 'info',
        }
    return {
        'label': f'{reference_count} Pod Reference' if reference_count == 1 else f'{reference_count} Pod References',
        'supporting': 'Committed Pod snapshot evidence',
        'tone': 'normal',
    }
