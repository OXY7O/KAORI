from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class TopologySelection:
    scope: str
    depth: str
    include_level_1: bool
    include_level_2: bool
    include_pods: bool
    include_all_relationships: bool
    show_compute: bool
    show_networking: bool
    show_configuration: bool
    show_storage: bool

    @classmethod
    def from_filters(cls, *, scope: str, depth: str) -> TopologySelection:
        return cls(
            scope=scope,
            depth=depth,
            include_level_1=True,
            include_level_2=depth in {'2', '3', 'full'},
            include_pods=depth in {'3', 'full'},
            include_all_relationships=depth == 'full',
            show_compute=scope in {'all', 'compute'},
            show_networking=scope in {'all', 'networking'},
            show_configuration=scope in {'all', 'configuration'},
            show_storage=scope in {'all', 'storage'},
        )


@dataclass(slots=True)
class TopologyRecords:
    clusters: list[Any]
    cluster_by_id: dict[str, Any]
    latest_cluster_inventory: dict[str, Any]
    namespaces: list[Any]
    nodes: list[Any]
    workloads: list[Any]
    services: list[Any]
    ingresses: list[Any]
    configurations: list[Any]
    storage_items: list[Any]
    pods: list[Any]


@dataclass(frozen=True, slots=True)
class TopologyNodeSpec:
    element_id: str
    label: str
    resource_type: str
    kind: str
    status: str
    status_tone: str
    cluster_id: str
    cluster_name: str
    namespace: str | None
    parent: str | None
    fields: list[dict[str, str]]
    collected_at: datetime | None
    action_url: str | None
    description: str


@dataclass(frozen=True, slots=True)
class TopologyEdgeSpec:
    edge_id: str
    source: str
    target: str
    relationship: str
    label: str
    source_label: str
    target_label: str
    description: str


@dataclass(slots=True)
class TopologyGraphState:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    collected_values: list[datetime] = field(default_factory=list)
    cluster_node_ids: dict[str, str] = field(default_factory=dict)
    namespace_node_ids: dict[tuple[str, str], str] = field(default_factory=dict)
    node_node_ids: dict[tuple[str, str], str] = field(default_factory=dict)
    workload_node_ids: dict[tuple[str, str, str, str], str] = field(default_factory=dict)
    service_node_ids: dict[tuple[str, str, str], str] = field(default_factory=dict)
    ingress_node_ids: dict[tuple[str, str, str], str] = field(default_factory=dict)
    config_node_ids: dict[tuple[str, str, str, str], str] = field(default_factory=dict)
    pvc_node_ids: dict[tuple[str, str, str], str] = field(default_factory=dict)
    pv_node_ids: dict[tuple[str, str], str] = field(default_factory=dict)
    pod_node_ids: dict[tuple[str, str, str], str] = field(default_factory=dict)
