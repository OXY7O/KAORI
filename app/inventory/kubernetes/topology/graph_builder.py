from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.inventory.kubernetes.topology.contracts import TopologyGraphState, TopologyRecords, TopologySelection
from app.inventory.kubernetes.topology.edge_builder import TopologyEdgeBuilder
from app.inventory.kubernetes.topology.node_builder import TopologyNodeBuilder
from app.inventory.kubernetes.topology.presentation import iso_datetime, limit_graph, normalize_datetime


class TopologyGraphBuilder:
    def __init__(
        self,
        records: TopologyRecords,
        selection: TopologySelection,
        *,
        max_nodes: int,
    ) -> None:
        self.records = records
        self.selection = selection
        self.max_nodes = max_nodes
        self.state = TopologyGraphState()

    def build(self, *, filters: dict[str, str], scope_label: str, depth_label: str) -> dict[str, Any]:
        TopologyNodeBuilder(self.records, self.selection, self.state).build()
        TopologyEdgeBuilder(self.records, self.selection, self.state).build()
        nodes, edges, omitted_nodes, omitted_by_type = limit_graph(
            self.state.nodes,
            self.state.edges,
            self.max_nodes,
        )
        return self._payload(
            nodes=nodes,
            edges=edges,
            omitted_nodes=omitted_nodes,
            omitted_by_type=omitted_by_type,
            filters=filters,
            scope_label=scope_label,
            depth_label=depth_label,
        )

    def _payload(
        self,
        *,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        omitted_nodes: int,
        omitted_by_type: dict[str, int],
        filters: dict[str, str],
        scope_label: str,
        depth_label: str,
    ) -> dict[str, Any]:
        type_counts: dict[str, int] = defaultdict(int)
        for node in nodes:
            type_counts[node['data']['type']] += 1

        collected = [
            normalized for value in self.state.collected_values if (normalized := normalize_datetime(value)) is not None
        ]
        latest_collected = max(collected, default=None)
        cluster_count = type_counts.get('cluster', 0)
        namespace_count = type_counts.get('namespace', 0)

        return {
            'nodes': nodes,
            'edges': edges,
            'summary': {
                'clusters': cluster_count,
                'namespaces': namespace_count,
                'resources': max(len(nodes) - cluster_count - namespace_count, 0),
                'relationships': len(edges),
                'last_collected_at': iso_datetime(latest_collected),
                'scope_label': scope_label,
                'depth_label': depth_label,
                'truncated': omitted_nodes > 0,
                'omitted_nodes': omitted_nodes,
                'omitted_by_type': omitted_by_type,
            },
            'type_counts': dict(type_counts),
            'filters': filters,
        }
