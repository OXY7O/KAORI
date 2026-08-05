from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.inventory.topology.contracts import (
    TopologyEdgeSpec,
    TopologyGraphState,
    TopologyRecords,
    TopologySelection,
)
from app.inventory.topology.presentation import edge_element, selector_matches


class TopologyEdgeBuilder:
    def __init__(
        self,
        records: TopologyRecords,
        selection: TopologySelection,
        state: TopologyGraphState,
    ) -> None:
        self.records = records
        self.selection = selection
        self.state = state
        self.pods_by_scope = self._pods_by_scope()

    def build(self) -> None:
        if self.selection.include_pods and self.selection.show_compute:
            self.add_compute_edges()
        if self.selection.show_networking and self.selection.include_level_2:
            self.add_ingress_routes()
            if self.selection.include_pods:
                self.add_service_selectors()
        if self.selection.show_configuration and self.selection.include_pods:
            self.add_configuration_edges()
        if self.selection.show_storage and self.selection.include_level_2:
            self.add_storage_bindings()
            if self.selection.include_pods:
                self.add_pod_mounts()
        self.apply_depth_policy()

    def add_compute_edges(self) -> None:
        for pod in self.records.pods:
            pod_id = self._pod_id(pod)
            if not pod_id:
                continue
            self._add_workload_owner(pod, pod_id)
            self._add_node_placement(pod, pod_id)

    def _add_workload_owner(self, pod: Any, pod_id: str) -> None:
        if not pod.workload_type or not pod.workload_name:
            return
        key = (pod.cluster_id, pod.namespace, pod.workload_type, pod.workload_name)
        workload_id = self.state.workload_node_ids.get(key)
        if not workload_id:
            return
        self._append(
            TopologyEdgeSpec(
                edge_id=f'owns:{workload_id}:{pod_id}',
                source=workload_id,
                target=pod_id,
                relationship='owns',
                label='owns',
                source_label=pod.workload_name,
                target_label=pod.pod_name,
                description='The workload controller owns this pod instance.',
            )
        )

    def _add_node_placement(self, pod: Any, pod_id: str) -> None:
        node_id = self.state.node_node_ids.get((pod.cluster_id, pod.node_name or ''))
        if not node_id:
            return
        self._append(
            TopologyEdgeSpec(
                edge_id=f'scheduled:{pod_id}:{node_id}',
                source=pod_id,
                target=node_id,
                relationship='scheduled_on',
                label='scheduled on',
                source_label=pod.pod_name,
                target_label=pod.node_name or 'Node',
                description='The Kubernetes scheduler placed this pod on the selected node.',
            )
        )

    def add_ingress_routes(self) -> None:
        for ingress in self.records.ingresses:
            ingress_id = self.state.ingress_node_ids.get(
                (ingress.cluster_id, ingress.namespace, ingress.ingress_name)
            )
            if not ingress_id:
                continue
            for index, backend in enumerate(ingress.backend_paths or []):
                service_name = str(backend.get('service_name') or '').strip()
                service_id = self.state.service_node_ids.get(
                    (ingress.cluster_id, ingress.namespace, service_name)
                )
                if not service_id:
                    continue
                self._append(
                    TopologyEdgeSpec(
                        edge_id=f'routes:{ingress_id}:{service_id}:{index}',
                        source=ingress_id,
                        target=service_id,
                        relationship='routes_to',
                        label='routes to',
                        source_label=ingress.ingress_name,
                        target_label=service_name,
                        description=(
                            f'Ingress path {backend.get("path") or "/"} routes to Service '
                            f'{service_name}:{backend.get("service_port") or "-"}'
                        ),
                    )
                )

    def add_service_selectors(self) -> None:
        for service in self.records.services:
            service_id = self.state.service_node_ids.get(
                (service.cluster_id, service.namespace, service.service_name)
            )
            if not service_id or not service.selector:
                continue
            for pod in self.pods_by_scope.get((service.cluster_id, service.namespace), []):
                pod_id = self._pod_id(pod)
                if not pod_id or not selector_matches(service.selector or {}, pod.labels or {}):
                    continue
                self._append(
                    TopologyEdgeSpec(
                        edge_id=f'selects:{service_id}:{pod_id}',
                        source=service_id,
                        target=pod_id,
                        relationship='selects',
                        label='selects',
                        source_label=service.service_name,
                        target_label=pod.pod_name,
                        description='The Service selector matches the labels recorded on this pod.',
                    )
                )

    def add_configuration_edges(self) -> None:
        for pod in self.records.pods:
            pod_id = self._pod_id(pod)
            if not pod_id:
                continue
            for index, reference in enumerate(pod.configuration_references or []):
                object_type = str(reference.get('type') or '').strip()
                object_name = str(reference.get('name') or '').strip()
                config_id = self.state.config_node_ids.get(
                    (pod.cluster_id, pod.namespace, object_type, object_name)
                )
                if not config_id:
                    continue
                self._append(
                    TopologyEdgeSpec(
                        edge_id=f'uses:{pod_id}:{config_id}:{index}',
                        source=pod_id,
                        target=config_id,
                        relationship='uses',
                        label='uses',
                        source_label=pod.pod_name,
                        target_label=object_name,
                        description=f'The pod references this {object_type} through its configuration.',
                    )
                )

    def add_storage_bindings(self) -> None:
        for pvc in self.records.storage_items:
            if pvc.storage_type != 'PersistentVolumeClaim' or not pvc.namespace:
                continue
            pvc_id = self.state.pvc_node_ids.get((pvc.cluster_id, pvc.namespace, pvc.name))
            if not pvc_id:
                continue
            volume_name = str((pvc.details or {}).get('volume_name') or '').strip()
            pv_id = self.state.pv_node_ids.get((pvc.cluster_id, volume_name))
            if not pv_id:
                continue
            self._append(
                TopologyEdgeSpec(
                    edge_id=f'binds:{pvc_id}:{pv_id}',
                    source=pvc_id,
                    target=pv_id,
                    relationship='binds',
                    label='binds',
                    source_label=pvc.name,
                    target_label=volume_name,
                    description='The PersistentVolumeClaim is bound to this PersistentVolume.',
                )
            )

    def add_pod_mounts(self) -> None:
        for pod in self.records.pods:
            pod_id = self._pod_id(pod)
            if not pod_id:
                continue
            for index, claim_name in enumerate(pod.persistent_volume_claims or []):
                pvc_id = self.state.pvc_node_ids.get((pod.cluster_id, pod.namespace, claim_name))
                if not pvc_id:
                    continue
                self._append(
                    TopologyEdgeSpec(
                        edge_id=f'mounts:{pod_id}:{pvc_id}:{index}',
                        source=pod_id,
                        target=pvc_id,
                        relationship='mounts',
                        label='mounts',
                        source_label=pod.pod_name,
                        target_label=claim_name,
                        description='The pod mounts storage provided by this PersistentVolumeClaim.',
                    )
                )

    def apply_depth_policy(self) -> None:
        if self.selection.include_all_relationships:
            return
        if self.selection.scope != 'all' or self.selection.depth != '3':
            return
        allowed = {'owns', 'scheduled_on', 'selects', 'routes_to'}
        self.state.edges = [edge for edge in self.state.edges if edge['data']['relationship'] in allowed]

    def _pod_id(self, pod: Any) -> str | None:
        return self.state.pod_node_ids.get((pod.cluster_id, pod.namespace, pod.pod_name))

    def _pods_by_scope(self) -> dict[tuple[str, str], list[Any]]:
        result: dict[tuple[str, str], list[Any]] = defaultdict(list)
        for pod in self.records.pods:
            result[(pod.cluster_id, pod.namespace)].append(pod)
        return result

    def _append(self, spec: TopologyEdgeSpec) -> None:
        self.state.edges.append(edge_element(spec))
