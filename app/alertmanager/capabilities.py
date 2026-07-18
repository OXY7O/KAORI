from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: str
    label: str
    category: str
    description: str
    required: bool = False


CAPABILITIES: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition('status_v2', 'Status API', 'api', 'Reads Alertmanager runtime and build information.', True),
    CapabilityDefinition('alerts_v2', 'Alerts API', 'api', 'Reads active alerts from Alertmanager API v2.', True),
    CapabilityDefinition('silences_v2', 'Silences API', 'api', 'Reads silence inventory and matcher metadata.', True),
    CapabilityDefinition('alert_labels', 'Alert labels', 'metadata', 'Alert payload exposes a labels mapping.', True),
    CapabilityDefinition('alertname_label', 'Alert name label', 'metadata', 'Observed alerts include the alertname label.', True),
    CapabilityDefinition('severity_label', 'Severity label', 'metadata', 'Observed alerts include a severity label.'),
    CapabilityDefinition('fingerprint', 'Fingerprint', 'metadata', 'Observed alerts include a stable fingerprint.'),
    CapabilityDefinition('starts_at', 'Start timestamp', 'metadata', 'Observed alerts include startsAt.'),
    CapabilityDefinition('receiver_metadata', 'Receiver metadata', 'metadata', 'Observed alerts identify their receiver.'),
    CapabilityDefinition('summary_annotation', 'Summary annotation', 'metadata', 'Observed alerts include annotations.summary.'),
    CapabilityDefinition('runbook_url', 'Runbook URL', 'metadata', 'Observed alerts expose a runbook link.'),
    CapabilityDefinition('generator_url', 'Generator URL', 'metadata', 'Observed alerts expose their generator URL.'),
    CapabilityDefinition('silence_matchers', 'Silence matchers', 'metadata', 'Observed silences expose matcher definitions.'),
)

CAPABILITY_BY_KEY = {item.key: item for item in CAPABILITIES}
