from __future__ import annotations

from typing import Any

from app.analytics.storage.evidence import VectorEvidence, sample_metric, sample_value

_CANONICAL_NODE_LABELS = ('node', 'nodename', 'kubernetes_node')


def node_numeric_map(evidence: VectorEvidence) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in evidence.rows:
        metric = sample_metric(item)
        node = next(
            (
                str(metric.get(label) or '').strip()
                for label in _CANONICAL_NODE_LABELS
                if str(metric.get(label) or '').strip()
            ),
            '',
        )
        value = sample_value(item)
        if not node or value is None:
            continue
        values[node] = max(values.get(node, value), value)
    return values


def claim_numeric_map(evidence: VectorEvidence) -> dict[str, float]:
    return _numeric_map(
        evidence,
        primary='persistentvolumeclaim',
        secondary='namespace',
    )


def volume_numeric_map(evidence: VectorEvidence) -> dict[str, float]:
    return _numeric_map(evidence, primary='persistentvolume')


def _numeric_map(
    evidence: VectorEvidence,
    *,
    primary: str,
    secondary: str | None = None,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in evidence.rows:
        metric = sample_metric(item)
        name = str(metric.get(primary) or '').strip()
        namespace = str(metric.get(secondary) or '').strip() if secondary else ''
        value = sample_value(item)
        if not name or value is None or (secondary and not namespace):
            continue
        key = f'{namespace}/{name}' if secondary else name
        values[key] = max(values.get(key, value), value)
    return values


def claim_phase_map(evidence: VectorEvidence) -> dict[str, str]:
    return _phase_map(
        evidence,
        primary='persistentvolumeclaim',
        secondary='namespace',
    )


def volume_phase_map(evidence: VectorEvidence) -> dict[str, str]:
    return _phase_map(evidence, primary='persistentvolume')


def _phase_map(
    evidence: VectorEvidence,
    *,
    primary: str,
    secondary: str | None = None,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in evidence.rows:
        if sample_value(item) != 1:
            continue
        metric = sample_metric(item)
        name = str(metric.get(primary) or '').strip()
        namespace = str(metric.get(secondary) or '').strip() if secondary else ''
        phase = str(metric.get('phase') or '').strip()
        if not name or not phase or (secondary and not namespace):
            continue
        key = f'{namespace}/{name}' if secondary else name
        values[key] = phase
    return values


def pvc_info_map(evidence: VectorEvidence) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    for item in evidence.rows:
        metric = sample_metric(item)
        namespace = str(metric.get('namespace') or '').strip()
        name = str(metric.get('persistentvolumeclaim') or '').strip()
        if not namespace or not name:
            continue
        values[f'{namespace}/{name}'] = {
            'storage_class': str(metric.get('storageclass') or '').strip(),
            'volume_name': str(metric.get('volumename') or '').strip(),
        }
    return values


def pv_info_map(evidence: VectorEvidence) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    for item in evidence.rows:
        metric = sample_metric(item)
        volume = str(metric.get('persistentvolume') or '').strip()
        if not volume:
            continue
        values[volume] = {
            'storage_class': str(metric.get('storageclass') or '').strip(),
            'reclaim_policy': str(
                metric.get('reclaim_policy') or metric.get('reclaimpolicy') or ''
            ).strip(),
        }
    return values


def pv_claim_map(evidence: VectorEvidence) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in evidence.rows:
        metric = sample_metric(item)
        namespace = str(metric.get('namespace') or '').strip()
        claim = str(metric.get('persistentvolumeclaim') or '').strip()
        volume = str(metric.get('volumename') or '').strip()
        if namespace and claim and volume:
            values[volume] = f'{namespace}/{claim}'
    return values


def split_claim_key(key: str) -> tuple[str, str]:
    if '/' not in key:
        return '', key
    namespace, name = key.split('/', 1)
    return namespace, name
