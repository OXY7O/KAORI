from __future__ import annotations

from typing import Any

from sqlalchemy import func

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.intelligence.alert_signals.service import (
    KUBERNETES_RUNTIME_HEALTH_PROFILE,
    runtime_signal_payloads,
)
from app.intelligence.catalog import minimum_severity_band_value, severity_for_observed_value
from app.intelligence.finding_evidence import build_restart_evidence, build_restart_groups


def _clone_rule_as_finding(
    rule: dict[str, Any],
    *,
    finding_key: str,
    title: str,
    summary: str,
    condition_summary: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    finding = dict(rule)
    finding.update(
        {
            'rule_key': finding_key,
            'title': title,
            'summary': summary,
            'condition_summary': condition_summary,
            'status': 'available',
            'evidence': evidence,
        }
    )
    return finding


def _runtime_signal_context(*rules: dict[str, Any] | None) -> tuple[dict[str, dict[str, Any]], set[str]]:
    enabled = any(
        str((rule or {}).get('alert_signal_profile') or '') == KUBERNETES_RUNTIME_HEALTH_PROFILE for rule in rules
    )
    return runtime_signal_payloads() if enabled else ({}, set())


def _inventory_pod_runtime_rows(
    *,
    restart_threshold: int,
    override_clusters: set[str],
) -> tuple[list[Any], list[Any]]:
    from app.models.inventory import PodInventory

    unhealthy_query = db.session.query(
        PodInventory.cluster_id,
        PodInventory.namespace,
        PodInventory.phase,
        func.count(PodInventory.id),
    ).filter(PodInventory.phase.notin_(['Running', 'Succeeded']))
    unhealthy_rows = [
        row
        for row in (
            filter_current_generation(unhealthy_query, PodInventory)
            .group_by(PodInventory.cluster_id, PodInventory.namespace, PodInventory.phase)
            .all()
        )
        if str(row[0]) not in override_clusters
    ]
    restart_query = db.session.query(
        PodInventory.cluster_id,
        PodInventory.namespace,
        PodInventory.pod_name,
        PodInventory.restart_count,
        PodInventory.phase,
        PodInventory.node_name,
        PodInventory.workload_type,
        PodInventory.workload_name,
    ).filter(PodInventory.restart_count >= restart_threshold)
    restart_rows = [
        row
        for row in filter_current_generation(restart_query, PodInventory).all()
        if str(row[0]) not in override_clusters
    ]
    return unhealthy_rows, restart_rows


def _merge_fast_pod_rows(
    *,
    fast_payloads: dict[str, dict[str, Any]],
    restart_threshold: int,
    unhealthy_rows: list[Any],
    restart_rows: list[Any],
) -> tuple[dict[tuple[str, str, str], int], list[Any]]:
    unhealthy_counts: dict[tuple[str, str, str], int] = {
        (str(cluster_id), str(namespace or 'default'), str(phase or 'Unknown')): int(count)
        for cluster_id, namespace, phase, count in unhealthy_rows
    }
    for cluster_id, payload in fast_payloads.items():
        for pod in list(payload.get('pods') or []):
            if not isinstance(pod, dict):
                continue
            namespace = str(pod.get('namespace') or 'default')
            phase = str(pod.get('phase') or 'Unknown')
            restart_count = int(pod.get('restart_count') or 0)
            if phase not in {'Running', 'Succeeded'}:
                key = (str(cluster_id), namespace, phase)
                unhealthy_counts[key] = unhealthy_counts.get(key, 0) + 1
            if restart_count >= restart_threshold:
                restart_rows.append(
                    (
                        str(cluster_id),
                        namespace,
                        str(pod.get('pod_name') or 'pod'),
                        restart_count,
                        phase,
                        str(pod.get('node_name') or ''),
                        '',
                        '',
                    )
                )
    return unhealthy_counts, restart_rows


def _unhealthy_pod_findings(
    rule: dict[str, Any] | None,
    *,
    unhealthy_counts: dict[tuple[str, str, str], int],
    fast_clusters: set[str],
) -> list[dict[str, Any]]:
    if not rule:
        return []
    findings: list[dict[str, Any]] = []
    for (cluster_id, namespace, phase), count in unhealthy_counts.items():
        fast = cluster_id in fast_clusters
        findings.append(
            _clone_rule_as_finding(
                rule,
                finding_key=f'kubernetes.pod.unhealthy_phase:{cluster_id}:{namespace}:{phase}',
                title=f'{count} pod{"s" if count != 1 else ""} in {namespace} are {phase or "not healthy"}',
                summary=(
                    f'{"Fast alert signal" if fast else "Pod inventory"} shows {count} '
                    f'pod{"s" if count != 1 else ""} in phase {phase or "Unknown"}.'
                ),
                condition_summary=(
                    'Fresh Kubernetes runtime signal reports a pod phase outside Running or Succeeded.'
                    if fast
                    else 'Collected pod phase is not Running or Succeeded.'
                ),
                evidence={
                    'cluster_id': cluster_id,
                    'namespace': namespace,
                    'affected_count': count,
                    'phase': phase,
                    'observed_total_display': f'{count} affected pod{"" if count == 1 else "s"}',
                    'evidence_window': (
                        'Latest fast Kubernetes alert signal' if fast else 'Latest committed inventory snapshot'
                    ),
                    'snapshot_basis': (
                        'Kubernetes Runtime Health signal' if fast else 'Current Pod Inventory generation'
                    ),
                },
            )
        )
    return findings


def _restart_findings(
    rule: dict[str, Any] | None,
    *,
    restart_rows: list[Any],
    restart_threshold: int,
    fast_clusters: set[str],
) -> list[dict[str, Any]]:
    if not rule:
        return []
    findings: list[dict[str, Any]] = []
    for (cluster_id, namespace), assets in build_restart_groups(restart_rows).items():
        fast = cluster_id in fast_clusters
        evidence = build_restart_evidence(
            cluster_id=cluster_id,
            namespace=namespace,
            assets=assets,
            threshold=restart_threshold,
            evidence_window='Latest fast Kubernetes alert signal' if fast else 'Latest committed inventory snapshot',
            snapshot_basis='Kubernetes Runtime Health signal' if fast else 'Current Pod Inventory generation',
        )
        affected_count = int(evidence['affected_count'])
        max_restarts = int(evidence['max_restart_count'])
        max_pod = str(evidence['max_restart_pod'])
        finding_severity = severity_for_observed_value(rule, max_restarts)
        findings.append(
            _clone_rule_as_finding(
                {**rule, 'severity': finding_severity},
                finding_key=f'kubernetes.pod.high_restart_count:{cluster_id}:{namespace}',
                title=(
                    f'Pod {max_pod} reports {max_restarts} restarts'
                    if affected_count == 1
                    else f'{affected_count} pods in {namespace} have repeated restarts (max {max_restarts})'
                ),
                summary=(
                    f'{"Latest fast Kubernetes alert signal" if fast else "Latest committed Pod Inventory"} '
                    f'shows {affected_count} affected pod{"" if affected_count == 1 else "s"}; '
                    f'{max_pod} has the highest observed restart count at {max_restarts}, with '
                    f'{evidence["total_restart_count"]} total restarts across the affected set.'
                ),
                condition_summary=(
                    f'Each affected pod has restart_count greater than or equal to {restart_threshold} '
                    'in the latest fast Kubernetes alert signal.'
                    if fast
                    else (
                        f'Each affected pod has restart_count greater than or equal to {restart_threshold} '
                        'in the latest committed Pod Inventory generation.'
                    )
                ),
                evidence=evidence,
            )
        )
    return findings


def _pod_health_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    unhealthy_rule = rules.get('kubernetes.pod.unhealthy_phase')
    restart_rule = rules.get('kubernetes.pod.high_restart_count')
    if not unhealthy_rule and not restart_rule:
        return []
    restart_threshold = minimum_severity_band_value(restart_rule, default=5) if restart_rule else 5
    fast_payloads, unavailable_clusters = _runtime_signal_context(unhealthy_rule, restart_rule)
    fast_clusters = set(fast_payloads)
    unhealthy_rows, restart_rows = _inventory_pod_runtime_rows(
        restart_threshold=restart_threshold,
        override_clusters=fast_clusters | unavailable_clusters,
    )
    unhealthy_counts, restart_rows = _merge_fast_pod_rows(
        fast_payloads=fast_payloads,
        restart_threshold=restart_threshold,
        unhealthy_rows=unhealthy_rows,
        restart_rows=restart_rows,
    )
    return [
        *_unhealthy_pod_findings(unhealthy_rule, unhealthy_counts=unhealthy_counts, fast_clusters=fast_clusters),
        *_restart_findings(
            restart_rule,
            restart_rows=restart_rows,
            restart_threshold=restart_threshold,
            fast_clusters=fast_clusters,
        ),
    ]


def _inventory_node_counts(override_clusters: set[str]) -> dict[str, int]:
    from app.models.inventory import NodeInventory

    query = db.session.query(NodeInventory.cluster_id, func.count(NodeInventory.id)).filter(
        NodeInventory.status != 'Ready'
    )
    return {
        str(cluster_id): int(count)
        for cluster_id, count in (
            filter_current_generation(query, NodeInventory).group_by(NodeInventory.cluster_id).all()
        )
        if str(cluster_id) not in override_clusters
    }


def _node_readiness_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rule = rules.get('kubernetes.node.not_ready')
    if not rule:
        return []
    fast_payloads, unavailable_clusters = _runtime_signal_context(rule)
    fast_clusters = set(fast_payloads)
    counts = _inventory_node_counts(fast_clusters | unavailable_clusters)
    for cluster_id, payload in fast_payloads.items():
        count = sum(
            1 for node in list(payload.get('nodes') or []) if isinstance(node, dict) and not bool(node.get('ready'))
        )
        if count:
            counts[str(cluster_id)] = count
    return [
        _clone_rule_as_finding(
            rule,
            finding_key=f'kubernetes.node.not_ready:{cluster_id}',
            title=f'{count} node{"s" if count != 1 else ""} are not Ready',
            summary=(
                f'{"Fast Kubernetes alert signal" if cluster_id in fast_clusters else "Node inventory"} shows '
                f'{count} node{"s" if count != 1 else ""} outside Ready state.'
            ),
            condition_summary=(
                'Fresh Kubernetes runtime signal reports one or more nodes outside Ready state.'
                if cluster_id in fast_clusters
                else 'Collected node status is not Ready.'
            ),
            evidence={
                'cluster_id': cluster_id,
                'affected_count': count,
                'evidence_window': (
                    'Latest fast Kubernetes alert signal'
                    if cluster_id in fast_clusters
                    else 'Latest committed inventory snapshot'
                ),
                'snapshot_basis': (
                    'Kubernetes Runtime Health signal'
                    if cluster_id in fast_clusters
                    else 'Current Node Inventory generation'
                ),
            },
        )
        for cluster_id, count in counts.items()
    ]


def build_kubernetes_runtime_recommendation_findings(
    rules: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build fast-path Kubernetes runtime findings without accelerating full inventory."""

    return [*_pod_health_findings(rules), *_node_readiness_findings(rules)]
