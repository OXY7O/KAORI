from __future__ import annotations

import logging
from typing import Any, cast

from kubernetes.client import V1NodeList
from kubernetes.client.rest import ApiException

from app.common.integration_errors import describe_integration_failure
from app.kubernetes.client import KubernetesClient
from app.kubernetes.tls import legacy_tls_context

logger = logging.getLogger(__name__)


def test_cluster_connection(
    kubeconfig_content: str,
    *,
    endpoint: str | None = None,
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
            'reason': None,
            'failure_code': None,
            'endpoint_host': None,
            'endpoint_port': None,
            'request_path': None,
        }

    except ApiException as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Kubernetes API',
            endpoint=endpoint,
            request_path='/api/v1/nodes',
        )
        logger.warning(
            'Kubernetes API connection test failed: %s',
            exc,
            exc_info=True,
        )

        return {
            'success': False,
            'node_count': 0,
            'error': failure['detail'],
            'reason': failure['reason'],
            'failure_code': failure['code'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        }

    except Exception as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Kubernetes API',
            endpoint=endpoint,
            request_path='/api/v1/nodes',
        )
        logger.exception(
            'Unexpected Kubernetes connection test failure.',
        )

        return {
            'success': False,
            'node_count': 0,
            'error': failure['detail'],
            'reason': failure['reason'],
            'failure_code': failure['code'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        }
