from __future__ import annotations

from typing import cast

from kubernetes.client import CoreV1Api, V1Node, V1NodeList, VersionApi
from kubernetes.client.models.version_info import VersionInfo


def get_cluster_version(
    api: CoreV1Api,
) -> str:
    version_api = VersionApi(
        api.api_client,
    )

    version = cast(
        VersionInfo,
        version_api.get_code(),
    )

    return version.git_version or 'unknown'


def get_nodes(
    api: CoreV1Api,
) -> list[V1Node]:
    result = cast(
        V1NodeList,
        api.list_node(),
    )

    if result.items is None:
        return []

    return result.items
