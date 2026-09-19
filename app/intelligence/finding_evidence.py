from __future__ import annotations

from typing import Any


def _restart_asset(
    *,
    namespace: str,
    pod_name: str,
    restart_count: int,
    phase: str,
    node_name: str,
    workload_type: str,
    workload_name: str,
) -> dict[str, Any]:
    return {
        'type': 'Pod',
        'name': pod_name,
        'namespace': namespace,
        'workload_type': workload_type,
        'workload_name': workload_name,
        'node_name': node_name,
        'phase': phase,
        'restart_count': restart_count,
        'evidence_display': f'{restart_count} restart{"" if restart_count == 1 else "s"}',
    }


def build_restart_groups(rows: list[Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for cluster_id, namespace, pod_name, restart_count, phase, node_name, workload_type, workload_name in rows:
        resolved_namespace = str(namespace or 'default')
        key = (str(cluster_id), resolved_namespace)
        groups.setdefault(key, []).append(
            _restart_asset(
                namespace=resolved_namespace,
                pod_name=str(pod_name or 'pod'),
                restart_count=int(restart_count or 0),
                phase=str(phase or 'Unknown'),
                node_name=str(node_name or ''),
                workload_type=str(workload_type or ''),
                workload_name=str(workload_name or ''),
            )
        )
    for assets in groups.values():
        assets.sort(key=lambda asset: int(asset.get('restart_count') or 0), reverse=True)
    return groups


def build_restart_evidence(
    *,
    cluster_id: str,
    namespace: str,
    assets: list[dict[str, Any]],
    threshold: int,
    evidence_window: str = 'Latest committed inventory snapshot',
    snapshot_basis: str = 'Current Pod Inventory generation',
) -> dict[str, Any]:
    affected_count = len(assets)
    total_restarts = sum(int(asset.get('restart_count') or 0) for asset in assets)
    highest = max(assets, key=lambda asset: int(asset.get('restart_count') or 0))
    highest_count = int(highest.get('restart_count') or 0)
    highest_name = str(highest.get('name') or 'pod')
    return {
        'cluster_id': cluster_id,
        'namespace': namespace,
        'affected_count': affected_count,
        'restart_threshold': threshold,
        'total_restart_count': total_restarts,
        'max_restart_count': highest_count,
        'max_restart_pod': highest_name,
        'threshold_display': f'>= {threshold} restarts per pod',
        'observed_total_display': (
            f'{total_restarts} restarts across {affected_count} affected pod{"" if affected_count == 1 else "s"}'
        ),
        'max_observation_display': f'{highest_count} restarts',
        'max_observation_asset': highest_name,
        'evidence_window': evidence_window,
        'snapshot_basis': snapshot_basis,
        'affected_assets': assets,
    }
