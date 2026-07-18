from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModuleRequirement:
    key: str
    label: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()


MODULE_REQUIREMENTS: tuple[ModuleRequirement, ...] = (
    ModuleRequirement('alert_inventory', 'Alert Inventory', ('alerts_v2', 'alert_labels', 'alertname_label', 'starts_at')),
    ModuleRequirement('silence_visibility', 'Silence Visibility', ('silences_v2',), ('silence_matchers',)),
    ModuleRequirement('kubernetes_alerts', 'Kubernetes Alerts', ('alerts_v2', 'alert_labels', 'alertname_label'), ('severity_label', 'fingerprint', 'summary_annotation')),
    ModuleRequirement('alert_intelligence', 'Alert Intelligence', ('alerts_v2', 'alert_labels', 'alertname_label', 'fingerprint'), ('receiver_metadata', 'severity_label')),
    ModuleRequirement('recommendations', 'Recommendations', ('alerts_v2', 'alert_labels'), ('summary_annotation', 'runbook_url')),
    ModuleRequirement('runbook_integration', 'Runbook Integration', ('alerts_v2', 'runbook_url')),
)


def evaluate_module_readiness(capabilities: Iterable[str]) -> list[dict[str, object]]:
    observed = set(capabilities)
    rows: list[dict[str, object]] = []
    for requirement in MODULE_REQUIREMENTS:
        missing_required = [key for key in requirement.required_capabilities if key not in observed]
        missing_optional = [key for key in requirement.optional_capabilities if key not in observed]
        if missing_required:
            status = 'unavailable'
        elif missing_optional:
            status = 'degraded'
        else:
            status = 'ready'
        rows.append({
            'key': requirement.key,
            'label': requirement.label,
            'status': status,
            'missing_required': missing_required,
            'missing_optional': missing_optional,
        })
    return rows
