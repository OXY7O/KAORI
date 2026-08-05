from __future__ import annotations

from dataclasses import dataclass
from typing import Final

INVENTORY_WORKBOOK_STANDARD: Final = 'kaori-inventory-xlsx-v2.0'
INVENTORY_WORKBOOK_FAMILY: Final = 'inventory'
INVENTORY_DATA_SHEET: Final = 'Inventory'
INVENTORY_METADATA_SHEET: Final = 'Metadata'
INVENTORY_DICTIONARY_SHEET: Final = 'Field Dictionary'


@dataclass(frozen=True, slots=True)
class InventoryColumn:
    key: str
    label: str
    definition: str
    data_type: str = 'text'
    source: str = 'Committed inventory snapshot'
    missing_value_rule: str = 'Not Available'
    width: float = 18.0
    number_format: str | None = None
    semantic_type: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryWorkbookProfile:
    report_type: str
    title: str
    description: str
    columns: tuple[InventoryColumn, ...]
    row_source: str = 'inventory_assets'
    identity_columns: tuple[str, ...] = ()


def column(
    key: str,
    label: str,
    definition: str,
    *,
    data_type: str = 'text',
    source: str = 'Committed inventory snapshot',
    missing_value_rule: str = 'Not Available',
    width: float = 18.0,
    number_format: str | None = None,
    semantic_type: str | None = None,
) -> InventoryColumn:
    return InventoryColumn(
        key=key,
        label=label,
        definition=definition,
        data_type=data_type,
        source=source,
        missing_value_rule=missing_value_rule,
        width=width,
        number_format=number_format,
        semantic_type=semantic_type,
    )


COMMON_CLUSTER_COLUMNS = (
    column('cluster', 'Cluster', 'Committed cluster display name.', width=22),
    column('environment', 'Environment', 'Environment associated with the cluster.', width=16),
)

COMMON_NAMESPACE_COLUMNS = (
    *COMMON_CLUSTER_COLUMNS,
    column('namespace', 'Namespace', 'Committed Kubernetes namespace.', width=22),
)

CREATED_AT_COLUMN = column(
    'created_at',
    'Created At',
    'Kubernetes resource creation timestamp when present.',
    data_type='datetime',
    missing_value_rule='Not Available',
    width=20,
    number_format='yyyy-mm-dd hh:mm',
)

COLLECTED_AT_COLUMN = column(
    'collected_at',
    'Last Collected',
    'Timestamp of the committed inventory row.',
    data_type='datetime',
    missing_value_rule='Not Available',
    width=20,
    number_format='yyyy-mm-dd hh:mm',
)


INVENTORY_WORKBOOK_PROFILES: dict[str, InventoryWorkbookProfile] = {
    'inventory_overview': InventoryWorkbookProfile(
        report_type='inventory_overview',
        title='Inventory Overview',
        description=(
            'Committed Kubernetes inventory totals by asset category. '
            'The workbook contains asset facts only and excludes analytical findings and recommendations.'
        ),
        identity_columns=('resource_type',),
        columns=(
            column('resource_type', 'Resource Category', 'Committed Kubernetes inventory category.', width=24),
            column(
                'assets',
                'Total Assets',
                'Number of committed assets in the selected scope.',
                data_type='integer',
                missing_value_rule='Blank',
                width=14,
                number_format='#,##0',
            ),
            column('status', 'Inventory Status', 'Current committed inventory publication state.', width=17, semantic_type='inventory_state'),
            column(
                'cluster_scope',
                'Cluster Scope',
                'Number of clusters represented by the category.',
                data_type='integer',
                missing_value_rule='Blank',
                width=14,
                number_format='#,##0',
            ),
            column(
                'namespace_scope',
                'Namespace Scope',
                'Number of namespaces represented by the category when applicable.',
                data_type='integer',
                missing_value_rule='Blank',
                width=16,
                number_format='#,##0',
            ),
            COLLECTED_AT_COLUMN,
        ),
    ),
    'node_inventory': InventoryWorkbookProfile(
        report_type='node_inventory',
        title='Nodes Inventory',
        description='Committed Kubernetes node identities, readiness, platform, capacity, addressing, and collection evidence.',
        identity_columns=('cluster', 'environment', 'node'),
        columns=(
            *COMMON_CLUSTER_COLUMNS,
            column('node', 'Node', 'Committed node identity.', width=34),
            column('role', 'Role', 'Committed node role label.', width=16),
            column('ready', 'Ready', 'Committed Kubernetes Ready condition.', width=12, semantic_type='readiness'),
            column('inventory_status', 'Inventory Status', 'Current, Stale, or Unavailable inventory state.', width=17, semantic_type='inventory_state'),
            column('scheduling_state', 'Scheduling State', 'Schedulable or unschedulable state.', width=18, semantic_type='scheduling'),
            column('cpu', 'CPU Capacity (cores)', 'Committed node CPU capacity.', data_type='integer', missing_value_rule='Blank', width=18, number_format='0'),
            column('memory', 'Memory Capacity', 'Committed node memory capacity.', width=18),
            column('ephemeral_storage', 'Ephemeral Storage', 'Committed node ephemeral storage capacity.', width=18),
            column('kubelet_version', 'Kubernetes Version', 'Committed kubelet version.', width=20),
            column('container_runtime', 'Container Runtime', 'Committed container runtime and version.', width=24),
            column('operating_system', 'Operating System', 'Committed operating-system identity.', width=22),
            column('architecture', 'Architecture', 'Committed node architecture.', width=14),
            column('internal_ip', 'Internal IP', 'Committed node internal IP.', width=16),
            column('external_ip', 'External IP', 'Committed node external IP when present.', width=16),
            column('memory_pressure', 'Memory Pressure', 'Committed MemoryPressure condition.', width=16, semantic_type='negative_condition'),
            column('disk_pressure', 'Disk Pressure', 'Committed DiskPressure condition.', width=16, semantic_type='negative_condition'),
            column('pid_pressure', 'PID Pressure', 'Committed PIDPressure condition.', width=14, semantic_type='negative_condition'),
            column('network_unavailable', 'Network Unavailable', 'Committed NetworkUnavailable condition.', width=19, semantic_type='negative_condition'),
            column('taints', 'Taints', 'Committed node taints.', width=34),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'namespace_inventory': InventoryWorkbookProfile(
        report_type='namespace_inventory',
        title='Namespaces Inventory',
        description='Committed namespace identities, lifecycle state, controls, and service-account posture.',
        identity_columns=('cluster', 'environment', 'namespace'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('status', 'Status', 'Committed namespace lifecycle status.', width=14, semantic_type='lifecycle'),
            column('uid', 'UID', 'Committed namespace UID.', width=28),
            column('labels', 'Label Count', 'Number of committed namespace labels.', data_type='integer', missing_value_rule='Blank', width=13, number_format='0'),
            column('annotations', 'Annotation Count', 'Number of committed namespace annotations.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('limit_ranges', 'LimitRange Count', 'Number of LimitRange resources.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('network_policies', 'NetworkPolicy Count', 'Number of NetworkPolicy resources.', data_type='integer', missing_value_rule='Blank', width=18, number_format='0'),
            column('service_accounts', 'ServiceAccount Count', 'Number of ServiceAccount resources.', data_type='integer', missing_value_rule='Blank', width=19, number_format='0'),
            column('default_service_account', 'Default ServiceAccount', 'Whether the default ServiceAccount is present.', width=20, semantic_type='presence'),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'workload_inventory': InventoryWorkbookProfile(
        report_type='workload_inventory',
        title='Workloads Inventory',
        description='Committed Kubernetes workload identities, readiness, replica state, and update strategy.',
        identity_columns=('cluster', 'environment', 'namespace', 'name'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('name', 'Workload', 'Committed workload name.', width=30),
            column('resource_type', 'Type', 'Committed workload kind.', width=18),
            column('ready', 'Ready', 'Committed workload readiness.', width=12, semantic_type='readiness'),
            column('status', 'Status', 'Committed workload runtime status.', width=16, semantic_type='lifecycle'),
            column('update_strategy', 'Update Strategy', 'Committed update or rollout strategy.', width=20),
            column('desired_replicas', 'Desired Replicas', 'Committed desired replica count.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('available_replicas', 'Available Replicas', 'Committed available replica count.', data_type='integer', missing_value_rule='Blank', width=17, number_format='0'),
            column('updated_replicas', 'Updated Replicas', 'Committed updated replica count.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('unavailable_replicas', 'Unavailable Replicas', 'Committed unavailable replica count.', data_type='integer', missing_value_rule='Blank', width=18, number_format='0'),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'pod_inventory': InventoryWorkbookProfile(
        report_type='pod_inventory',
        title='Pods Inventory',
        description='Committed pod identities, ownership, phase, readiness, placement, restarts, and attached evidence.',
        identity_columns=('cluster', 'environment', 'namespace', 'pod'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('pod', 'Pod', 'Committed pod identity.', width=34),
            column('resource_type', 'Workload Type', 'Owning workload kind or Standalone.', width=18),
            column('workload', 'Workload', 'Owning workload name.', width=28),
            column('status', 'Phase', 'Committed pod phase.', width=14, semantic_type='lifecycle'),
            column('ready', 'Ready', 'Committed pod readiness.', width=12, semantic_type='readiness'),
            column('restarts', 'Restarts', 'Committed aggregate container restart count.', data_type='integer', missing_value_rule='Blank', width=12, number_format='0'),
            column('node', 'Node', 'Committed node placement.', width=32),
            column('pod_ip', 'Pod IP', 'Committed pod IP.', width=16),
            column('container_count', 'Containers', 'Number of committed containers.', data_type='integer', missing_value_rule='Blank', width=13, number_format='0'),
            column('image_count', 'Images', 'Number of committed regular, init, and ephemeral image references.', data_type='integer', missing_value_rule='Blank', width=11, number_format='0'),
            column('configuration_references', 'Configuration References', 'Number of ConfigMap/Secret references.', data_type='integer', missing_value_rule='Blank', width=21, number_format='0'),
            column('persistent_volume_claims', 'PVC References', 'Number of PVC references.', data_type='integer', missing_value_rule='Blank', width=15, number_format='0'),
            column('qos_class', 'QoS Class', 'Committed Kubernetes QoS class.', width=15),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'service_inventory': InventoryWorkbookProfile(
        report_type='service_inventory',
        title='Services Inventory',
        description='Committed Kubernetes Service identities, access models, port mappings, selectors, traffic policy, and backend registration evidence.',
        identity_columns=('cluster', 'environment', 'namespace', 'name'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('name', 'Service', 'Committed Service identity.', width=30),
            column('resource_type', 'Type', 'Effective Service type, including Headless.', width=16),
            column('access_model', 'Access Model', 'Factual Service access model; publication does not prove reachability.', width=25),
            column('status', 'Backend Registration', 'Endpoint registration evidence state.', width=22, semantic_type='inventory_state'),
            column('cluster_ip', 'Cluster IP', 'Committed cluster IP or headless identity.', width=18),
            column('external_ip', 'External Addresses', 'Declared external IPs and load-balancer addresses.', width=28),
            column('external_name', 'External Name', 'ExternalName DNS target when configured.', width=28),
            column('ports', 'Port Mappings', 'Committed Service, target, protocol, and NodePort mappings.', width=40),
            column('port_count', 'Port Count', 'Number of declared Service ports.', data_type='integer', missing_value_rule='Blank', width=12, number_format='0'),
            column('selector_count', 'Selector Count', 'Number of selector fields.', data_type='integer', missing_value_rule='Blank', width=14, number_format='0'),
            column('selector', 'Selector', 'Committed Service selector.', width=36),
            column('endpoint_source', 'Endpoint Source', 'EndpointSlice, Endpoints, or Not Applicable.', width=18),
            column('ready_endpoints', 'Ready Endpoints', 'Number of reported ready backend addresses.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('not_ready_endpoints', 'Not-Ready Endpoints', 'Number of reported not-ready backend addresses.', data_type='integer', missing_value_rule='Blank', width=18, number_format='0'),
            column('load_balancer', 'Load Balancer Addresses', 'Committed load-balancer ingress addresses.', width=28),
            column('internal_traffic_policy', 'Internal Traffic Policy', 'Committed internal traffic policy.', width=22),
            column('external_traffic_policy', 'External Traffic Policy', 'Committed external traffic policy.', width=22),
            column('publish_not_ready', 'Publish Not-Ready', 'Whether not-ready addresses are published.', data_type='boolean', width=18),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'ingress_inventory': InventoryWorkbookProfile(
        report_type='ingress_inventory',
        title='Ingress Inventory',
        description='Committed Kubernetes Ingress identity, host scope, controller publication, backend routes, and TLS Secret references.',
        identity_columns=('cluster', 'environment', 'namespace', 'name'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('name', 'Ingress', 'Committed Ingress identity.', width=30),
            column('ingress_class', 'Ingress Class', 'Explicit class value or Not Explicitly Set.', width=24),
            column('ingress_class_source', 'Class Evidence', 'Source of the class declaration.', width=30),
            column('host_scope', 'Host Scope', 'Primary explicit host, All Hosts, or evidence state.', width=32),
            column('hosts', 'Explicit Hosts', 'Committed explicit host declarations.', width=42),
            column('all_host_rule_count', 'All-Host Rules', 'Rules without an explicit host.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('publication_status', 'Publication Status', 'Published, Address Pending, or Not Reported.', width=20, semantic_type='status'),
            column('addresses', 'Controller Addresses', 'Committed controller-published addresses or evidence state.', width=34),
            column('address_count', 'Address Count', 'Number of committed controller addresses when publication evidence was reported.', data_type='integer', missing_value_rule='Blank', width=15, number_format='0'),
            column('tls_enabled', 'TLS Declared', 'Whether committed Ingress TLS configuration exists.', data_type='boolean', width=15, semantic_type='tls_enabled'),
            column('tls_status', 'TLS Reference State', 'TLS Referenced, TLS declared without a Secret, or no TLS declaration.', width=20, semantic_type='tls_status'),
            column('tls_secret_count', 'TLS Secret References', 'Number of distinct committed TLS Secret references.', data_type='integer', missing_value_rule='Blank', width=20, number_format='0'),
            column('tls_hosts', 'TLS Hosts', 'Hosts declared by committed TLS entries.', width=40),
            column('backend_count', 'Backend Routes', 'Number of committed rule paths and default backends.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('service_backend_count', 'Service Backends', 'Number of distinct committed Service backend references.', data_type='integer', missing_value_rule='Blank', width=18, number_format='0'),
            column('resource_backend_count', 'Resource Backends', 'Number of committed resource backend declarations.', data_type='integer', missing_value_rule='Blank', width=19, number_format='0'),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'configuration_inventory': InventoryWorkbookProfile(
        report_type='configuration_inventory',
        title='Configuration Inventory',
        description='Committed ConfigMap and Secret identities and metadata. Secret values are never exported.',
        identity_columns=('cluster', 'environment', 'namespace', 'name'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('name', 'Name', 'Committed ConfigMap or Secret identity.', width=32),
            column('resource_type', 'Object Type', 'ConfigMap or Secret.', width=16),
            column('secret_type', 'Secret Type', 'Committed Kubernetes Secret type when applicable.', width=28),
            column('key_count', 'Key Count', 'Number of committed key names.', data_type='integer', missing_value_rule='Blank', width=13, number_format='0'),
            column('key_names', 'Key Names', 'Committed key names only; values are excluded.', width=40),
            column('immutable', 'Immutable', 'Committed immutable flag.', data_type='boolean', width=13),
            column('payload_size_bytes', 'Payload Size (bytes)', 'Committed aggregate payload size without exporting values.', data_type='integer', missing_value_rule='Blank', width=19, number_format='#,##0'),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'storage_inventory': InventoryWorkbookProfile(
        report_type='storage_inventory',
        title='Storage Inventory',
        description='Committed StorageClass, persistent-volume, and persistent-volume-claim identities and lifecycle fields.',
        identity_columns=('cluster', 'environment', 'namespace', 'name'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('name', 'Name', 'Committed storage resource identity.', width=32),
            column('resource_type', 'Type', 'StorageClass, PersistentVolume, or PersistentVolumeClaim.', width=24),
            column('status', 'Lifecycle', 'Canonical committed storage lifecycle state.', width=17, semantic_type='lifecycle'),
            column('storage_class', 'Storage Class', 'Committed StorageClass reference.', width=24),
            column('requested_capacity', 'Requested Capacity', 'PVC requested storage when reported.', width=20),
            column('reported_capacity', 'Reported Capacity', 'PV capacity or PVC bound capacity when reported.', width=20),
            column('requested_access_modes', 'Requested Access Modes', 'Requested PVC or configured PV access modes.', width=24),
            column('reported_access_modes', 'Reported Access Modes', 'PVC status access modes when reported.', width=24),
            column('volume_mode', 'Volume Mode', 'Committed volume mode.', width=16),
            column('binding_reference', 'Binding Reference', 'Claim, volume, or provisioning-class binding identity.', width=32),
            column('reclaim_policy', 'Reclaim Policy', 'Committed reclaim policy.', width=17),
            column('binding_mode', 'Binding Mode', 'StorageClass volume-binding mode.', width=20),
            column('volume_expansion', 'Volume Expansion', 'Allowed, Not Allowed, Not Reported, or Not Applicable.', width=20),
            column('provisioner', 'Provisioner', 'Committed StorageClass provisioner.', width=30),
            column('volume_source', 'Volume Source', 'PersistentVolume source type when reported.', width=22),
            column('specification_evidence', 'Specification Evidence', 'Whether Kubernetes specification evidence was reported.', width=23),
            column('status_evidence', 'Status Evidence', 'Whether Kubernetes lifecycle status evidence was reported.', width=20),
            CREATED_AT_COLUMN,
            COLLECTED_AT_COLUMN,
        ),
    ),
    'tls_inventory': InventoryWorkbookProfile(
        report_type='tls_inventory',
        title='TLS Certificate Inventory',
        description=(
            'Committed TLS certificate metadata, validity window, usage references, hostname coverage, and collection evidence. '
            'Private keys and Secret values are excluded.'
        ),
        row_source='records',
        identity_columns=('cluster', 'environment', 'namespace', 'secret_name'),
        columns=(
            *COMMON_NAMESPACE_COLUMNS,
            column('secret_name', 'Secret Name', 'Committed Kubernetes TLS Secret name.', width=30),
            column('secret_type', 'Secret Type', 'Committed Kubernetes Secret type.', width=24),
            column('common_name', 'Common Name', 'Certificate common name when present.', width=30),
            column('issuer', 'Issuer', 'Certificate issuer.', width=38),
            column('serial_number', 'Serial Number', 'Certificate serial number.', width=26),
            column('fingerprint_sha256', 'SHA-256 Fingerprint', 'Committed certificate SHA-256 fingerprint.', width=48),
            column('dns_names_label', 'DNS Names', 'Committed certificate DNS SAN values.', width=42),
            column('ingress_hosts_label', 'Ingress Hosts', 'Committed Ingress host relationships.', width=42),
            column('not_before', 'Not Before', 'Certificate validity start.', data_type='datetime', width=20, number_format='yyyy-mm-dd hh:mm'),
            column('not_after', 'Not After', 'Certificate expiry timestamp.', data_type='datetime', width=20, number_format='yyyy-mm-dd hh:mm'),
            column('days_remaining', 'Days Remaining', 'Calendar days from data cut-off to notAfter.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('status_label', 'Validity Status', 'Valid, Renewal Window, Critical Expiry, Expired, Invalid, or Unknown.', width=18, semantic_type='certificate_status'),
            column('usage_label', 'Usage Status', 'In Use, Unused, or Unknown Usage based on committed reference evidence.', width=17, semantic_type='usage_status'),
            column('reference_count', 'Reference Count', 'Number of committed consumers.', data_type='integer', missing_value_rule='Blank', width=16, number_format='0'),
            column('references_label', 'Referenced By', 'Committed Ingress/resource identities.', width=40),
            column('coverage_label', 'Hostname Coverage', 'Committed hostname coverage state.', width=20, semantic_type='coverage_status'),
            column('declared_host_count', 'Declared Hosts', 'Number of declared hosts.', data_type='integer', missing_value_rule='Blank', width=15, number_format='0'),
            column('covered_host_count', 'Covered Hosts', 'Number of declared hosts covered by SAN evidence.', data_type='integer', missing_value_rule='Blank', width=15, number_format='0'),
            column('uncovered_hosts_label', 'Uncovered Hosts', 'Declared hosts not covered by committed certificate SAN evidence.', width=40),
            column('parse_state', 'Parse State', 'Committed certificate parse result.', width=15, semantic_type='parse_status'),
            column('parse_error', 'Parse Error', 'Committed parse error when present.', width=42),
            COLLECTED_AT_COLUMN,
        ),
    ),
}

INVENTORY_XLSX_REPORT_TYPES = frozenset(INVENTORY_WORKBOOK_PROFILES)


def get_inventory_workbook_profile(report_type: str) -> InventoryWorkbookProfile:
    try:
        return INVENTORY_WORKBOOK_PROFILES[report_type]
    except KeyError as exc:
        raise ValueError(f'Unsupported Inventory Excel report type: {report_type}.') from exc
