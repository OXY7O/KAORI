from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.integrations.alertmanager.capabilities import CAPABILITY_BY_KEY


@dataclass(frozen=True, slots=True)
class ModuleRequirement:
    key: str
    label: str
    description: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    operator_guidance: str = ''


MODULE_REQUIREMENTS: tuple[ModuleRequirement, ...] = (
    ModuleRequirement(
        'alert_inventory',
        'Alert Inventory',
        'Provides canonical active-alert visibility, filtering, lifecycle context, and operational drill-down.',
        ('alerts_v2', 'alert_labels', 'alertname_label', 'starts_at'),
        operator_guidance='Restore Alerts API access and ensure representative alerts expose labels, alertname, and startsAt.',
    ),
    ModuleRequirement(
        'silence_visibility',
        'Silence Visibility',
        'Provides silence inventory, ownership context, matcher visibility, and suppression correlation.',
        ('silences_v2',),
        ('silence_matchers',),
        'Restore Silences API access. Add a controlled silence when matcher evidence must be verified.',
    ),
    ModuleRequirement(
        'kubernetes_alerts',
        'Infrastructure Alert Views',
        'Maps Alertmanager records into infrastructure-focused operational views using canonical labels.',
        ('alerts_v2', 'alert_labels', 'alertname_label'),
        ('severity_label', 'fingerprint', 'summary_annotation'),
        'Restore required alert payload fields first, then standardize severity, fingerprint, and summary metadata for richer views.',
    ),
    ModuleRequirement(
        'alert_intelligence',
        'Alert Intelligence',
        'Correlates repeated alerts, routing context, severity, and identity for analysis and prioritization.',
        ('alerts_v2', 'alert_labels', 'alertname_label', 'fingerprint'),
        ('receiver_metadata', 'severity_label'),
        'Ensure stable fingerprints and alert identity are available; enrich receiver and severity metadata for better correlation.',
    ),
    ModuleRequirement(
        'recommendations',
        'Recommendations',
        'Uses alert context to produce actionable operational recommendations and remediation links.',
        ('alerts_v2', 'alert_labels'),
        ('summary_annotation', 'runbook_url'),
        'Restore alert access and labels, then add summary and runbook annotations to improve recommendation quality.',
    ),
    ModuleRequirement(
        'runbook_integration',
        'Runbook Integration',
        'Links alert records directly to maintained operational procedures.',
        ('alerts_v2', 'runbook_url'),
        operator_guidance='Add a valid runbook URL annotation to representative alerts and rerun Full Validation.',
    ),
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
            'description': requirement.description,
            'status': status,
            'required_capabilities': list(requirement.required_capabilities),
            'optional_capabilities': list(requirement.optional_capabilities),
            'required_capability_labels': [CAPABILITY_BY_KEY[key].label for key in requirement.required_capabilities],
            'optional_capability_labels': [CAPABILITY_BY_KEY[key].label for key in requirement.optional_capabilities],
            'missing_required': missing_required,
            'missing_required_labels': [CAPABILITY_BY_KEY[key].label for key in missing_required],
            'missing_optional': missing_optional,
            'missing_optional_labels': [CAPABILITY_BY_KEY[key].label for key in missing_optional],
            'operator_guidance': requirement.operator_guidance,
        })
    return rows
