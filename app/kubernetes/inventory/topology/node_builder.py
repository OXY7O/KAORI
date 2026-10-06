from __future__ import annotations

from collections import defaultdict
from typing import Any

from flask import url_for

from app.kubernetes.cluster.constants import get_environment_label
from app.kubernetes.inventory.resources.ingress_semantics import (
    host_presentation as ingress_host_presentation,
)
from app.kubernetes.inventory.resources.ingress_semantics import (
    ingress_class_presentation,
)
from app.kubernetes.inventory.resources.ingress_semantics import (
    publication_presentation as ingress_publication_presentation,
)
from app.kubernetes.inventory.resources.storage_semantics import (
    binding_reference as storage_binding_reference,
)
from app.kubernetes.inventory.resources.storage_semantics import (
    lifecycle_presentation as storage_lifecycle_presentation,
)
from app.kubernetes.inventory.topology.contracts import (
    TopologyGraphState,
    TopologyNodeSpec,
    TopologyRecords,
    TopologySelection,
)
from app.kubernetes.inventory.topology.presentation import (
    field,
    node_element,
    selector_matches,
    status_tone,
)


class TopologyNodeBuilder:
    def __init__(
        self,
        records: TopologyRecords,
        selection: TopologySelection,
        state: TopologyGraphState,
    ) -> None:
        self.records = records
        self.selection = selection
        self.state = state
        self.services_by_scope = self._services_by_scope()

    def build(self) -> None:
        self.add_clusters()
        self.add_namespaces()
        if self.selection.include_level_1 and self.selection.show_compute:
            self.add_nodes()
        if self.selection.include_level_2 and self.selection.show_compute:
            self.add_workloads()
        if self.selection.include_level_2 and self.selection.show_networking:
            self.add_services()
            self.add_ingresses()
        if self.selection.include_level_2 and self.selection.show_configuration:
            self.add_configurations()
        if self.selection.include_level_2 and self.selection.show_storage:
            self.add_storage()
        if self.selection.include_pods:
            self.add_pods()

    def add_clusters(self) -> None:
        for cluster in self.records.clusters:
            element_id = f'cluster:{cluster.id}'
            inventory = self.records.latest_cluster_inventory.get(cluster.id)
            self.state.cluster_node_ids[cluster.id] = element_id
            spec = TopologyNodeSpec(
                element_id=element_id,
                label=cluster.name,
                resource_type='cluster',
                kind='Cluster',
                status=cluster.status or 'Unknown',
                status_tone=status_tone(cluster.status, 'cluster'),
                cluster_id=cluster.id,
                cluster_name=cluster.name,
                namespace=None,
                parent=None,
                fields=[
                    field('Environment', get_environment_label(cluster.environment)),
                    field('Status', cluster.status),
                    field(
                        'API Server', cluster.kubernetes_connection.server if cluster.kubernetes_connection else None
                    ),
                    field('Kubernetes Version', inventory.kubernetes_version if inventory else None),
                    field('Nodes', cluster.node_count),
                ],
                collected_at=inventory.collected_at if inventory else cluster.updated_at,
                action_url=url_for('integrations.kubernetes'),
                description='Registered Kubernetes cluster and inventory snapshot boundary.',
            )
            self.state.nodes.append(node_element(spec))
            if inventory is not None:
                self.state.collected_values.append(inventory.collected_at)

    def add_namespaces(self) -> None:
        for item in self.records.namespaces:
            cluster = self.records.cluster_by_id[item.cluster_id]
            element_id = f'namespace:{item.id}'
            self.state.namespace_node_ids[(item.cluster_id, item.namespace)] = element_id
            self._append(
                TopologyNodeSpec(
                    element_id=element_id,
                    label=item.namespace,
                    resource_type='namespace',
                    kind='Namespace',
                    status=item.status or 'Unknown',
                    status_tone=status_tone(item.status, 'namespace'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=self.state.cluster_node_ids[item.cluster_id],
                    fields=[
                        field('Status', item.status),
                        field('Kubernetes UID', item.uid),
                        field('LimitRanges', item.limit_range_count, empty='0'),
                        field('NetworkPolicies', item.network_policy_count, empty='0'),
                        field('ServiceAccounts', item.service_account_count, empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.namespaces',
                        cluster_id=item.cluster_id,
                        search=item.namespace,
                    ),
                    description='Namespace boundary containing namespaced Kubernetes resources.',
                )
            )

    def add_nodes(self) -> None:
        for item in self.records.nodes:
            cluster = self.records.cluster_by_id[item.cluster_id]
            element_id = f'node:{item.id}'
            self.state.node_node_ids[(item.cluster_id, item.node_name)] = element_id
            self._append(
                TopologyNodeSpec(
                    element_id=element_id,
                    label=item.node_name,
                    resource_type='node',
                    kind='Node',
                    status=item.status or 'Unknown',
                    status_tone=status_tone(item.status, 'node'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=None,
                    parent=self.state.cluster_node_ids[item.cluster_id],
                    fields=[
                        field('Role', item.role),
                        field('Status', item.status),
                        field('Internal IP', item.internal_ip),
                        field('Operating System', item.os_image),
                        field('Kubelet Version', item.kubelet_version),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for('inventory.nodes', cluster_id=item.cluster_id, search=item.node_name),
                    description='Kubernetes node used for workload placement and scheduling.',
                )
            )

    def add_workloads(self) -> None:
        for item in self.records.workloads:
            parent = self.state.namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = self.records.cluster_by_id[item.cluster_id]
            element_id = f'workload:{item.id}'
            key = (item.cluster_id, item.namespace, item.workload_type, item.name)
            self.state.workload_node_ids[key] = element_id
            self._append(
                TopologyNodeSpec(
                    element_id=element_id,
                    label=item.name,
                    resource_type='workload',
                    kind=item.workload_type,
                    status=item.status or item.ready or 'Unknown',
                    status_tone=status_tone(item.status or item.ready, 'workload'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        field('Type', item.workload_type),
                        field('Status', item.status),
                        field('Ready', item.ready),
                        field('Namespace', item.namespace),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.workloads',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.name,
                    ),
                    description='Workload controller recorded in the latest inventory snapshot.',
                )
            )

    def add_services(self) -> None:
        for item in self.records.services:
            parent = self.state.namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = self.records.cluster_by_id[item.cluster_id]
            details = item.details or {}
            external_addresses = ', '.join(details.get('external_addresses') or [])
            port_mappings = ', '.join(
                f'{int(port.get("port") or 0)}/{port.get("protocol") or "TCP"}'
                for port in details.get('ports') or []
                if isinstance(port, dict)
            )
            element_id = f'service:{item.id}'
            self.state.service_node_ids[(item.cluster_id, item.namespace, item.service_name)] = element_id
            self._append(
                TopologyNodeSpec(
                    element_id=element_id,
                    label=item.service_name,
                    resource_type='service',
                    kind='Service',
                    status='Configured',
                    status_tone='info',
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        field('Type', item.service_type),
                        field('Cluster IP', item.cluster_ip),
                        field('External Address', external_addresses or None),
                        field('Ports', port_mappings or None),
                        field('Selector Labels', len(item.selector or {}), empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.services',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.service_name,
                    ),
                    description='Service exposing pods selected by Kubernetes labels.',
                )
            )

    def add_ingresses(self) -> None:
        for item in self.records.ingresses:
            parent = self.state.namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = self.records.cluster_by_id[item.cluster_id]
            element_id = f'ingress:{item.id}'
            self.state.ingress_node_ids[(item.cluster_id, item.namespace, item.ingress_name)] = element_id
            details = item.details or {}
            ingress_class, _ = ingress_class_presentation(
                item.ingress_class,
                details.get('ingress_class_source'),
            )
            host_scope, _, _ = ingress_host_presentation(details)
            publication = ingress_publication_presentation(details)
            has_routes = bool(item.backend_paths)
            status = publication['label'] if has_routes else 'No Backend Routes'
            tone = publication['tone'] if has_routes else 'warning'
            self._append(
                TopologyNodeSpec(
                    element_id=element_id,
                    label=item.ingress_name,
                    resource_type='ingress',
                    kind='Ingress',
                    status=status,
                    status_tone=tone,
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        field('Host Scope', host_scope),
                        field('Ingress Class', ingress_class),
                        field('Publication', publication['address']),
                        field('TLS Referenced', item.tls_enabled),
                        field('Backend Routes', len(item.backend_paths or []), empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.ingresses',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.ingress_name,
                    ),
                    description='Ingress routing external hosts and paths to Kubernetes Services.',
                )
            )

    def add_configurations(self) -> None:
        for item in self.records.configurations:
            parent = self.state.namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                continue
            cluster = self.records.cluster_by_id[item.cluster_id]
            object_type = item.object_type or 'Configuration'
            resource_type = 'secret' if object_type.lower() == 'secret' else 'configmap'
            element_id = f'configuration:{item.id}'
            key = (item.cluster_id, item.namespace, object_type, item.name)
            self.state.config_node_ids[key] = element_id
            self._append(
                TopologyNodeSpec(
                    element_id=element_id,
                    label=item.name,
                    resource_type=resource_type,
                    kind=object_type,
                    status='Immutable' if item.immutable else 'Mutable',
                    status_tone='info',
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        field('Object Type', object_type),
                        field('Secret Type', item.secret_type),
                        field('Keys', len(item.key_names or []), empty='0'),
                        field('Immutable', item.immutable),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.configuration',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        type=object_type,
                        search=item.name,
                    ),
                    description='Configuration object referenced by pods through volumes or environment sources.',
                )
            )

    def add_storage(self) -> None:
        for item in self.records.storage_items:
            spec = self._storage_spec(item)
            if spec is not None:
                self._append(spec)

    def _storage_spec(self, item: Any) -> TopologyNodeSpec | None:
        cluster = self.records.cluster_by_id[item.cluster_id]
        if item.storage_type == 'PersistentVolumeClaim':
            if not item.namespace:
                return None
            parent = self.state.namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent:
                return None
            resource_type = 'pvc'
            kind = 'PersistentVolumeClaim'
            element_id = f'pvc:{item.id}'
            self.state.pvc_node_ids[(item.cluster_id, item.namespace, item.name)] = element_id
            action_url = url_for(
                'inventory.storage',
                cluster_id=item.cluster_id,
                namespace=item.namespace,
                type=item.storage_type,
                search=item.name,
            )
        elif item.storage_type == 'PersistentVolume':
            parent = self.state.cluster_node_ids[item.cluster_id]
            resource_type = 'pv'
            kind = 'PersistentVolume'
            element_id = f'pv:{item.id}'
            self.state.pv_node_ids[(item.cluster_id, item.name)] = element_id
            action_url = url_for(
                'inventory.storage',
                cluster_id=item.cluster_id,
                type=item.storage_type,
                search=item.name,
            )
        else:
            return None

        details = item.details or {}
        lifecycle, lifecycle_tone = storage_lifecycle_presentation(
            item.storage_type,
            item.status,
            details,
        )
        return TopologyNodeSpec(
            element_id=element_id,
            label=item.name,
            resource_type=resource_type,
            kind=kind,
            status=lifecycle,
            status_tone=lifecycle_tone,
            cluster_id=item.cluster_id,
            cluster_name=cluster.name,
            namespace=item.namespace,
            parent=parent,
            fields=[
                field('Lifecycle', lifecycle),
                field('Storage Class', item.storage_class),
                field('Reported Capacity', item.capacity),
                field('Requested Capacity', details.get('requested_storage')),
                field('Binding Reference', storage_binding_reference(item.storage_type, details)),
            ],
            collected_at=item.collected_at,
            action_url=action_url,
            description='Persistent storage object and its current binding state.',
        )

    def add_pods(self) -> None:
        for item in self.records.pods:
            parent = self.state.namespace_node_ids.get((item.cluster_id, item.namespace))
            if not parent or not self._pod_is_relevant(item):
                continue
            cluster = self.records.cluster_by_id[item.cluster_id]
            element_id = f'pod:{item.id}'
            self.state.pod_node_ids[(item.cluster_id, item.namespace, item.pod_name)] = element_id
            owner = (
                f'{item.workload_type}/{item.workload_name}'
                if item.workload_type and item.workload_name
                else 'Standalone Pod'
            )
            self._append(
                TopologyNodeSpec(
                    element_id=element_id,
                    label=item.pod_name,
                    resource_type='pod',
                    kind='Pod',
                    status=item.phase or 'Unknown',
                    status_tone=status_tone(item.phase, 'pod'),
                    cluster_id=item.cluster_id,
                    cluster_name=cluster.name,
                    namespace=item.namespace,
                    parent=parent,
                    fields=[
                        field('Phase', item.phase),
                        field('Ready', item.ready),
                        field('Owner', owner),
                        field('Node', item.node_name),
                        field('Pod IP', item.pod_ip),
                        field('Restarts', item.restart_count, empty='0'),
                    ],
                    collected_at=item.collected_at,
                    action_url=url_for(
                        'inventory.pods',
                        cluster_id=item.cluster_id,
                        namespace=item.namespace,
                        search=item.pod_name,
                    ),
                    description='Pod instance with workload ownership, placement, and dependency references.',
                )
            )

    def _pod_is_relevant(self, pod: Any) -> bool:
        if self.selection.scope in {'all', 'compute'}:
            return True
        if self.selection.scope == 'networking':
            services = self.services_by_scope.get((pod.cluster_id, pod.namespace), [])
            return any(selector_matches(service.selector or {}, pod.labels or {}) for service in services)
        if self.selection.scope == 'configuration':
            return bool(pod.configuration_references)
        if self.selection.scope == 'storage':
            return bool(pod.persistent_volume_claims)
        return False

    def _services_by_scope(self) -> dict[tuple[str, str], list[Any]]:
        result: dict[tuple[str, str], list[Any]] = defaultdict(list)
        for service in self.records.services:
            result[(service.cluster_id, service.namespace)].append(service)
        return result

    def _append(self, spec: TopologyNodeSpec) -> None:
        self.state.nodes.append(node_element(spec))
        if spec.collected_at is not None:
            self.state.collected_values.append(spec.collected_at)
