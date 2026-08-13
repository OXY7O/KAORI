import logging
from collections.abc import Callable
from datetime import UTC, datetime

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
    allow_weak_tls = bool(connection.allow_weak_tls)
    collected_at = datetime.now(UTC)

    current_stage = 'cluster lock'
    _report_progress(progress_callback, 2, 'Preparing Cluster', 'Locking the committed inventory boundary.')

    try:
        _lock_cluster_inventory_sync(
            cluster.id,
        )

        with weak_tls_context(
            enabled=allow_weak_tls,
        ):
            _report_progress(
                progress_callback, 6, 'Preparing Kubernetes Client', 'Building the canonical Kubernetes API client.'
            )
            client = get_integration('kubernetes').execute('client.build', connection)

            core_api = client.core_api()

            apps_api = client.apps_api()

            batch_api = BatchV1Api(
                core_api.api_client,
            )

            networking_api = client.networking_api()

            discovery_api = DiscoveryV1Api(core_api.api_client)

            storage_api = client.storage_api()

            current_stage = 'API discovery'
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

            cronjob_items = None
            cronjob_adapter = adapters.get('inventory.cronjobs')
            if cronjob_adapter and cronjob_adapter.get('stability') == 'legacy':
                cronjob_items = list_cluster_resource(core_api.api_client, cronjob_adapter)

            ingress_items = None
            ingress_adapter = adapters.get('inventory.ingresses')
            if ingress_adapter and ingress_adapter.get('stability') == 'legacy':
                ingress_items = list_cluster_resource(core_api.api_client, ingress_adapter)

            current_stage = 'cluster information'
            _report_progress(
                progress_callback,
                20,
                'Collecting Cluster Metadata',
                'Collecting canonical cluster identity and platform metadata.',
            )
            save_cluster_info(
                cluster,
                collected_at,
                core_api,
            )
            db.session.flush()

            current_stage = 'nodes'
            _report_progress(
                progress_callback, 28, 'Collecting Nodes', 'Collecting node capacity, readiness, and runtime metadata.'
            )
            save_nodes(
                cluster,
                collected_at,
                core_api,
            )
            db.session.flush()

            current_stage = 'namespaces'
            _report_progress(
                progress_callback,
                36,
                'Collecting Namespaces',
                'Collecting namespaces and policy-related inventory evidence.',
            )
            save_namespaces(
                cluster,
                collected_at,
                core_api,
                networking_api,
            )
            db.session.flush()

            current_stage = 'workloads'
            _report_progress(
                progress_callback,
                46,
                'Collecting Workloads',
                'Collecting deployments, stateful workloads, jobs, and workload configuration.',
            )
            save_workloads(
                cluster,
                collected_at,
                apps_api,
                batch_api,
                cronjob_items=cronjob_items,
            )
            db.session.flush()

            current_stage = 'pods'
            _report_progress(
                progress_callback,
                58,
                'Collecting Pods',
                'Collecting pod placement, readiness, image, and runtime evidence.',
            )
            save_pods(
                cluster,
                collected_at,
                core_api,
                apps_api,
                batch_api,
            )
            db.session.flush()

            current_stage = 'services'
            _report_progress(
                progress_callback, 67, 'Collecting Services', 'Collecting Service and endpoint inventory evidence.'
            )
            save_services(
                cluster,
                collected_at,
                core_api,
                discovery_api,
            )
            db.session.flush()

            current_stage = 'ingresses'
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

            current_stage = 'storage'
            _report_progress(
                progress_callback,
                81,
                'Collecting Storage',
                'Collecting persistent volume, claim, and storage-class inventory.',
            )
            save_storage_inventory(
                cluster,
                collected_at,
                core_api,
                storage_api,
            )
            db.session.flush()

            current_stage = 'configuration'
            _report_progress(
                progress_callback,
                88,
                'Collecting Configuration Metadata',
                'Collecting ConfigMap and Secret key-index metadata without persisting secret values.',
            )
            save_configuration_inventory(
                cluster,
                collected_at,
                core_api,
                include_configmaps='inventory.configmaps' in adapters,
                include_secrets='inventory.secrets' in adapters,
            )
            db.session.flush()

            current_stage = 'resource quotas'
            _report_progress(
                progress_callback,
                94,
                'Collecting Resource Quotas',
                'Collecting namespace resource quota configuration and observed usage.',
            )
            save_resource_quotas(
                cluster,
                collected_at,
                core_api,
            )
            db.session.flush()

        current_stage = 'commit'
        _report_progress(
            progress_callback,
            98,
            'Committing Inventory Snapshot',
            'Promoting the complete Kubernetes inventory generation atomically.',
        )
        db.session.commit()
        _report_progress(
            progress_callback,
            100,
            'Cluster Snapshot Committed',
            'The committed Kubernetes inventory snapshot is current.',
        )

    except Exception:
        logger.exception(
            'Kubernetes inventory synchronization failed for cluster %s during %s.',
            cluster.id,
            current_stage,
        )
        db.session.rollback()
        raise
