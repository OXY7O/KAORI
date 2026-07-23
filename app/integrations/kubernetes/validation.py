from __future__ import annotations

import logging
from typing import Any, cast

from kubernetes.client import V1NodeList
from kubernetes.client.rest import ApiException

from app.common.integration_errors import describe_integration_failure
from app.integrations.compatibility import evaluate_compatibility, kubernetes_lifecycle
from app.integrations.kubernetes.client import KubernetesClient
from app.integrations.kubernetes.compatibility import KubernetesDiscovery
from app.integrations.kubernetes.tls import weak_tls_context

logger = logging.getLogger(__name__)


def test_cluster_runtime_health(
    kubeconfig_content: str,
    *,
    endpoint: str | None = None,
    verify_ssl: bool = True,
    allow_weak_tls: bool = False,
) -> dict[str, Any]:
    """Run a lightweight Kubernetes reachability probe.

    This deliberately avoids API discovery and node inventory so scheduled
    runtime monitoring does not rebuild the full capability contract.
    """
    try:
        with weak_tls_context(enabled=allow_weak_tls):
            client_factory = KubernetesClient(
                kubeconfig_content=kubeconfig_content,
                verify_ssl=verify_ssl,
            )
            version_info = client_factory.version_api().get_code()

        return {
            'success': True,
            'version': getattr(version_info, 'git_version', None) or 'unknown',
            'platform': getattr(version_info, 'platform', None),
            'message': 'Kubernetes API runtime health probe succeeded.',
            'error': None,
            'reason': None,
            'failure_code': None,
            'endpoint_host': None,
            'endpoint_port': None,
            'request_path': '/version',
        }
    except ApiException as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Kubernetes API',
            endpoint=endpoint,
            request_path='/version',
        )
        logger.warning('Kubernetes runtime health probe failed: %s', exc, exc_info=True)
        return {
            'success': False,
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
            request_path='/version',
        )
        logger.exception('Unexpected Kubernetes runtime health probe failure.')
        return {
            'success': False,
            'error': failure['detail'],
            'reason': failure['reason'],
            'failure_code': failure['code'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        }


def test_cluster_connection(
    kubeconfig_content: str,
    *,
    endpoint: str | None = None,
    verify_ssl: bool = True,
    allow_weak_tls: bool = False,
) -> dict[str, Any]:
    try:
        with weak_tls_context(
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

        readiness_reasons: list[str] = []
        if lifecycle == 'legacy':
            readiness_reasons.append(
                f'Kubernetes {git_version} is in the KAORI legacy lifecycle band. '
                'Stable APIs remain usable, but upgrade planning is required before readiness can return to Ready.'
            )
        if discovery['legacy_features']:
            readiness_reasons.append(
                'Legacy API adapters are selected for: ' + ', '.join(discovery['legacy_features']) + '.'
            )
        if discovery['blocked_features']:
            readiness_reasons.append(
                'Required capabilities are blocked for: ' + ', '.join(discovery['blocked_features']) + '.'
            )
        if compatibility.readiness == 'blocked':
            readiness_reasons.append(compatibility.message)

        discovery['lifecycle_status'] = lifecycle
        discovery['detected_version'] = git_version
        discovery['readiness_reasons'] = readiness_reasons

        messages = [compatibility.message]
        messages.extend(readiness_reasons)

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
