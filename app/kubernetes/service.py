from __future__ import annotations

from typing import Any, cast

from kubernetes.client import V1NodeList
from kubernetes.client.rest import ApiException

from app.kubernetes.client import KubernetesClient
from app.kubernetes.tls import legacy_tls_context


def test_cluster_connection(
    kubeconfig_content: str,
    *,
    verify_ssl: bool = True,
    allow_weak_tls: bool = False,
) -> dict[str, Any]:
    try:
        with legacy_tls_context(
            enabled=allow_weak_tls,
        ):
            api = KubernetesClient(
                kubeconfig_content=kubeconfig_content,
                verify_ssl=verify_ssl,
            ).connect()

            nodes = cast(
                V1NodeList,
                api.list_node(),
            )

        return {
            'success': True,
            'node_count': len(
                nodes.items or [],
            ),
            'error': None,
        }

    except ApiException as exc:
        error_message = str(
            exc,
        )

        print('=== KUBERNETES API EXCEPTION ===')
        print(error_message)

        return {
            'success': False,
            'node_count': 0,
            'error': error_message,
        }

    except Exception as exc:
        error_message = str(
            exc,
        )

        print('=== KUBERNETES CONNECTION EXCEPTION ===')
        print(type(exc).__name__)
        print(error_message)

        return {
            'success': False,
            'node_count': 0,
            'error': error_message,
        }
