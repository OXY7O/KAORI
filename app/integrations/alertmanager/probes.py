from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def discover_payload_capabilities(
    alerts: Sequence[Mapping[str, Any]],
    silences: Sequence[Mapping[str, Any]],
) -> set[str]:
    capabilities: set[str] = set()
    if alerts:
        capabilities.add('alert_labels')
    for alert in alerts:
        raw_labels = alert.get('labels')
        raw_annotations = alert.get('annotations')
        labels: Mapping[str, Any] = raw_labels if isinstance(raw_labels, Mapping) else {}
        annotations: Mapping[str, Any] = raw_annotations if isinstance(raw_annotations, Mapping) else {}
        if labels.get('alertname'):
            capabilities.add('alertname_label')
        if labels.get('severity'):
            capabilities.add('severity_label')
        if alert.get('fingerprint'):
            capabilities.add('fingerprint')
        if alert.get('startsAt'):
            capabilities.add('starts_at')
        if alert.get('receivers') or alert.get('receiver'):
            capabilities.add('receiver_metadata')
        if annotations.get('summary'):
            capabilities.add('summary_annotation')
        if annotations.get('runbook_url') or annotations.get('runbook'):
            capabilities.add('runbook_url')
        if alert.get('generatorURL'):
            capabilities.add('generator_url')
    if any(isinstance(item.get('matchers'), list) for item in silences):
        capabilities.add('silence_matchers')
    return capabilities
