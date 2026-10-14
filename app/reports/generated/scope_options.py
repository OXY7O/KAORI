from __future__ import annotations

from sqlalchemy import select

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.object_storage import ObjectStorageSystem
from app.reports.scope import (
    ARTIFACT_REGISTRY_INSTANCE_ASSET_TYPE,
    KUBERNETES_CLUSTER_ASSET_TYPE,
    OBJECT_STORAGE_SYSTEM_ASSET_TYPE,
    get_active_registry_options,
)


def get_scope_options() -> list[dict[str, str]]:
    clusters = (
        db.session.execute(
            select(
                Cluster,
            ).order_by(
                Cluster.name.asc(),
            )
        )
        .scalars()
        .all()
    )
    object_storage_systems = (
        db.session.execute(
            select(
                ObjectStorageSystem,
            ).order_by(
                ObjectStorageSystem.name.asc(),
            )
        )
        .scalars()
        .all()
    )

    options = [
        {
            'value': '',
            'label': 'All Infrastructure Assets',
        },
    ]

    for cluster in clusters:
        options.append(
            {
                'value': f'{KUBERNETES_CLUSTER_ASSET_TYPE}:{cluster.id}',
                'label': f'Kubernetes · {cluster.name}',
            }
        )

    for system in object_storage_systems:
        options.append(
            {
                'value': f'{OBJECT_STORAGE_SYSTEM_ASSET_TYPE}:{system.id}',
                'label': f'Object Storage · {system.name}',
            }
        )

    for instance in get_active_registry_options():
        options.append(
            {
                'value': f'{ARTIFACT_REGISTRY_INSTANCE_ASSET_TYPE}:{instance["value"]}',
                'label': f'Artifact Registry · {instance["label"]}',
            }
        )

    return options
