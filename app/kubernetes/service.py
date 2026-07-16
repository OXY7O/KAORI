from __future__ import annotations

import logging
from typing import Any, cast

from kubernetes.client import V1NodeList
from kubernetes.client.rest import ApiException

from app.common.integration_errors import describe_integration_failure
from app.kubernetes.client import KubernetesClient
from app.integrations.compatibility import evaluate_compatibility, kubernetes_lifecycle
from app.kubernetes.compatibility import KubernetesDiscovery
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
            client_factory = KubernetesClient(
                kubeconfig_content=kubeconfig_content,
                verify_ssl=verify_ssl,
            )
            api = client_factory.connect()
            nodes = cast(V1NodeList, api.list_node())
            version_info = client_factory.version_api().get_code()

        git_version = getattr(version_info, 'git_version', None) or 'unknown'
        platform = getattr(version_info, 'platform', None)
        compatibility = evaluate_compatibility('kubernetes', git_version)
        discovery = KubernetesDiscovery(api.api_client).discover()
        lifecycle = kubernetes_lifecycle(git_version)

        compatibility_status = discovery['compatibility_status']
        readiness_status = discovery['readiness_status']
        if compatibility.status == 'unsupported_version':
            compatibility_status = compatibility.status
            readiness_status = compatibility.readiness
        elif lifecycle == 'legacy' and compatibility_status == 'compatible':
            compatibility_status = 'compatible_with_warnings'
            readiness_status = 'degraded'

        messages = [compatibility.message]
        if discovery['legacy_features']:
            messages.append('Legacy adapters selected for: ' + ', '.join(discovery['legacy_features']))
        if discovery['blocked_features']:
            messages.append('Unavailable features: ' + ', '.join(discovery['blocked_features']))

        return {
            'success': True,
            'node_count': len(nodes.items or []),
            'version': git_version,
            'platform': platform,
            'compatibility_status': compatibility_status,
            'readiness_status': readiness_status,
            'compatibility_profile': discovery['api_profile'],
            'lifecycle_status': lifecycle,
            'api_discovery_summary': discovery,
            'validation_message': ' '.join(messages),
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
