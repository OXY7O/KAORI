from __future__ import annotations

from typing import Any, cast

from kubernetes.client import NetworkingV1Api, V1IngressList

from app.inventory.collectors.common import _metadata_details, _string_value, _to_modelish


def get_ingresses(
    api: NetworkingV1Api | None = None,
    *,
    ingress_items: list[Any] | None = None,
) -> list[dict]:
    if ingress_items is None:
        if api is None:
            return []
        result = cast(
            V1IngressList,
            api.list_ingress_for_all_namespaces(),
        )
        ingress_items = list(result.items or [])

    ingresses: list[dict] = []

    for raw_ingress in ingress_items:
        ingress = _to_modelish(raw_ingress)
        metadata = ingress.metadata
        spec = ingress.spec
        status = ingress.status

        if metadata is None:
            continue

        backend_paths: list[dict[str, str]] = []
        hosts: list[str] = []

        def _backend_to_dict(backend):
            service = getattr(backend, 'service', None)
            if service is not None:
                port = getattr(service, 'port', None)
                port_value = '-'
                if port is not None:
                    port_value = getattr(port, 'name', None) or getattr(port, 'number', None) or '-'
                return {
                    'service_name': getattr(service, 'name', None) or '-',
                    'service_port': str(port_value),
                }

            # networking/extensions v1beta1 schema
            return {
                'service_name': getattr(backend, 'service_name', None) or '-',
                'service_port': str(getattr(backend, 'service_port', None) or '-'),
            }

        default_backend = None
        if spec and spec.default_backend:
            default_backend = _backend_to_dict(spec.default_backend)
            backend_paths.append(
                {
                    'host': '-',
                    'path': '/',
                    'path_type': 'DefaultBackend',
                    **default_backend,
                }
            )

        if spec and spec.rules:
            for rule in spec.rules:
                rule_host = rule.host or '-'
                if rule_host != '-' and rule_host not in hosts:
                    hosts.append(rule_host)

                http_rule = getattr(rule, 'http', None)
                if not http_rule or not http_rule.paths:
                    continue

                for path in http_rule.paths:
                    backend_info = _backend_to_dict(path.backend)
                    backend_paths.append(
                        {
                            'host': rule_host,
                            'path': path.path or '/',
                            'path_type': path.path_type or '-',
                            **backend_info,
                        }
                    )

        addresses: list[str] = []
        if status and status.load_balancer and status.load_balancer.ingress:
            for item in status.load_balancer.ingress:
                value = item.ip or item.hostname
                if value and value not in addresses:
                    addresses.append(value)

        tls_entries: list[dict[str, Any]] = []
        if spec and spec.tls:
            for tls in spec.tls:
                tls_entries.append(
                    {
                        'secret_name': _string_value(getattr(tls, 'secret_name', None)),
                        'hosts': list(getattr(tls, 'hosts', None) or []),
                    }
                )

        metadata_details = _metadata_details(metadata)
        details = {
            **metadata_details,
            'generation': int(getattr(metadata, 'generation', 0) or 0),
            'hosts': hosts,
            'tls': tls_entries,
            'rule_count': len(spec.rules or []) if spec else 0,
            'default_backend': default_backend,
            'finalizers': list(getattr(metadata, 'finalizers', None) or []),
        }

        ingresses.append(
            {
                'namespace': metadata.namespace,
                'ingress_name': metadata.name,
                'ingress_class': (
                    spec.ingress_class_name
                    if spec and spec.ingress_class_name
                    else (metadata.annotations or {}).get('kubernetes.io/ingress.class')
                ),
                'host': hosts[0] if hosts else '-',
                'address': ', '.join(addresses) if addresses else '-',
                'tls_enabled': bool(tls_entries),
                'backend_paths': backend_paths,
                'details': details,
                'created_at': metadata.creation_timestamp,
            }
        )

    return ingresses
