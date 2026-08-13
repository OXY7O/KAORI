import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import BatchV1Api, DiscoveryV1Api
from sqlalchemy import select

from app.extensions.db import db
from app.integrations.kubernetes.compatibility import KubernetesDiscovery, list_cluster_resource
from app.integrations.kubernetes.tls import weak_tls_context
from app.integrations.registry import get_integration
from app.inventory.persistence import (
    save_cluster_info,
    save_configuration_inventory,
    save_ingresses,
    save_namespaces,
    save_nodes,
    save_pods,
    save_resource_quotas,
    save_services,
    save_storage_inventory,
    save_workloads,
)
from app.models import Cluster
from app.models.kubernetes import KubernetesConnection

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str, str], None]


@dataclass(slots=True)
class _InventoryRuntime:
    core_api: Any
    apps_api: Any
    batch_api: Any
    networking_api: Any
    discovery_api: Any
    storage_api: Any
    adapters: dict[str, Any]
    cronjob_items: Any
    ingress_adapter: Any
    ingress_items: Any


def _report_progress(
    callback: ProgressCallback | None,
    percent: int,
    stage: str,
    message: str,
) -> None:
    if callback is not None:
        callback(max(0, min(int(percent), 100)), stage, message)


def _lock_cluster_inventory_sync(
    cluster_id: str,
) -> None:
    """Serialize inventory replacement for one cluster within the DB transaction."""
    db.session.execute(
        select(Cluster.id)
        .where(
            Cluster.id == cluster_id,
        )
        .with_for_update(),
    ).scalar_one()




def _discover_inventory(
    connection: KubernetesConnection,
    progress_callback: ProgressCallback | None,
) -> _InventoryRuntime:
    _report_progress(
        progress_callback, 6, 'Preparing Kubernetes Client', 'Building the canonical Kubernetes API client.'
    )
    client = get_integration('kubernetes').execute('client.build', connection)
    core_api = client.core_api()
    _report_progress(
        progress_callback,
        12,
        'Discovering Kubernetes APIs',
        'Resolving supported API adapters and compatibility evidence.',
    )
    discovery = KubernetesDiscovery(core_api.api_client).discover()
    adapters = discovery['selected_adapters']
    connection.compatibility_profile = discovery['api_profile']
    connection.compatibility_status = discovery['compatibility_status']
    connection.readiness_status = discovery['readiness_status']
    connection.discovery_summary = discovery

    cronjob_adapter = adapters.get('inventory.cronjobs')
    cronjob_items = (
        list_cluster_resource(core_api.api_client, cronjob_adapter)
        if cronjob_adapter and cronjob_adapter.get('stability') == 'legacy'
        else None
    )
    ingress_adapter = adapters.get('inventory.ingresses')
    ingress_items = (
        list_cluster_resource(core_api.api_client, ingress_adapter)
        if ingress_adapter and ingress_adapter.get('stability') == 'legacy'
        else None
    )
    return _InventoryRuntime(
        core_api=core_api,
        apps_api=client.apps_api(),
        batch_api=BatchV1Api(core_api.api_client),
        networking_api=client.networking_api(),
        discovery_api=DiscoveryV1Api(core_api.api_client),
        storage_api=client.storage_api(),
        adapters=adapters,
        cronjob_items=cronjob_items,
        ingress_adapter=ingress_adapter,
        ingress_items=ingress_items,
    )


def _persist_inventory_resources(
    cluster: Cluster,
    collected_at: datetime,
    inventory: _InventoryRuntime,
    progress_callback: ProgressCallback | None,
    current_stage: list[str],
) -> None:
    core_api = inventory.core_api
    apps_api = inventory.apps_api
    batch_api = inventory.batch_api
    networking_api = inventory.networking_api
    discovery_api = inventory.discovery_api
    storage_api = inventory.storage_api
    adapters = inventory.adapters
    cronjob_items = inventory.cronjob_items
    ingress_adapter = inventory.ingress_adapter
    ingress_items = inventory.ingress_items

    steps = (
        ('cluster information', 20, 'Collecting Cluster Metadata',
         'Collecting canonical cluster identity and platform metadata.',
         lambda: save_cluster_info(cluster, collected_at, core_api)),
        ('nodes', 28, 'Collecting Nodes',
         'Collecting node capacity, readiness, and runtime metadata.',
         lambda: save_nodes(cluster, collected_at, core_api)),
        ('namespaces', 36, 'Collecting Namespaces',
         'Collecting namespaces and policy-related inventory evidence.',
         lambda: save_namespaces(cluster, collected_at, core_api, networking_api)),
        ('workloads', 46, 'Collecting Workloads',
         'Collecting deployments, stateful workloads, jobs, and workload configuration.',
         lambda: save_workloads(cluster, collected_at, apps_api, batch_api, cronjob_items=cronjob_items)),
        ('pods', 58, 'Collecting Pods',
         'Collecting pod placement, readiness, image, and runtime evidence.',
         lambda: save_pods(cluster, collected_at, core_api, apps_api, batch_api)),
        ('services', 67, 'Collecting Services',
         'Collecting Service and endpoint inventory evidence.',
         lambda: save_services(cluster, collected_at, core_api, discovery_api)),
        ('storage', 81, 'Collecting Storage',
         'Collecting persistent volume, claim, and storage-class inventory.',
         lambda: save_storage_inventory(cluster, collected_at, core_api, storage_api)),
        ('configuration', 88, 'Collecting Configuration Metadata',
         'Collecting ConfigMap and Secret key-index metadata without persisting secret values.',
         lambda: save_configuration_inventory(
             cluster, collected_at, core_api,
             include_configmaps='inventory.configmaps' in adapters,
             include_secrets='inventory.secrets' in adapters,
         )),
        ('resource quotas', 94, 'Collecting Resource Quotas',
         'Collecting namespace resource quota configuration and observed usage.',
         lambda: save_resource_quotas(cluster, collected_at, core_api)),
    )
    for stage, percent, title, message, persist in steps:
        current_stage[0] = stage
        _report_progress(progress_callback, percent, title, message)
        persist()
        db.session.flush()

    current_stage[0] = 'ingresses'
    _report_progress(
        progress_callback, 74, 'Collecting Ingresses', 'Collecting ingress routing and TLS exposure evidence.'
    )
    if ingress_adapter:
        save_ingresses(
            cluster,
            collected_at,
            networking_api if ingress_adapter.get('stability') == 'stable' else None,
            ingress_items=ingress_items,
        )
    db.session.flush()


def sync_inventory(
    cluster: Cluster,
    connection: KubernetesConnection,
    *,
    progress_callback: ProgressCallback | None = None,
) -> None:
    if connection.cluster_id != cluster.id:
        raise ValueError('The canonical Kubernetes connection does not belong to the selected cluster.')
    instance = connection.integration_instance
    if not instance.enabled or instance.lifecycle_status != 'active':
        raise RuntimeError('The canonical Kubernetes integration is not active for inventory synchronization.')

    collected_at = datetime.now(UTC)
    current_stage = ['cluster lock']
    _report_progress(progress_callback, 2, 'Preparing Cluster', 'Locking the committed inventory boundary.')
    try:
        _lock_cluster_inventory_sync(cluster.id)
        with weak_tls_context(enabled=bool(connection.allow_weak_tls)):
            current_stage[0] = 'API discovery'
            inventory = _discover_inventory(connection, progress_callback)
            _persist_inventory_resources(cluster, collected_at, inventory, progress_callback, current_stage)

        current_stage[0] = 'commit'
        _report_progress(
            progress_callback,
            98,
            'Committing Inventory Snapshot',
            'Promoting the complete Kubernetes inventory generation atomically.',
        )
        db.session.commit()
        _report_progress(
            progress_callback, 100, 'Cluster Snapshot Committed', 'The committed Kubernetes inventory snapshot is current.'
        )
    except Exception:
        logger.exception(
            'Kubernetes inventory synchronization failed for cluster %s during %s.',
            cluster.id,
            current_stage[0],
        )
        db.session.rollback()
        raise
