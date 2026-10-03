from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.models.tenant import TenantEnvironmentName, TenantResourceProfileClass

_TENANT_SLUG_RE = re.compile(r'[^a-z0-9-]+')
_ALLOWED_ENVIRONMENTS = {item.value for item in TenantEnvironmentName}
_ALLOWED_PROFILE_CLASSES = {item.value for item in TenantResourceProfileClass}
_ALLOWED_TENANT_PROVIDERS = {'native_kubernetes', 'capsule'}

RESOURCE_PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    'small': {
        'version': 2,
        'quota': {
            'requests.cpu': '1',
            'limits.cpu': '2',
            'requests.memory': '2Gi',
            'limits.memory': '4Gi',
            'pods': '10',
            'persistentvolumeclaims': '5',
            'requests.storage': '50Gi',
            'services': '5',
            'configmaps': '25',
            'secrets': '25',
        },
        'limits': {
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '250m', 'memory': '256Mi'},
        },
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
    },
    'standard': {
        'version': 2,
        'quota': {
            'requests.cpu': '2',
            'limits.cpu': '4',
            'requests.memory': '4Gi',
            'limits.memory': '8Gi',
            'pods': '20',
            'persistentvolumeclaims': '10',
            'requests.storage': '100Gi',
            'services': '10',
            'configmaps': '50',
            'secrets': '50',
        },
        'limits': {
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
            'default': {'cpu': '500m', 'memory': '512Mi'},
        },
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
    },
    'large': {
        'version': 2,
        'quota': {
            'requests.cpu': '4',
            'limits.cpu': '8',
            'requests.memory': '8Gi',
            'limits.memory': '16Gi',
            'pods': '40',
            'persistentvolumeclaims': '20',
            'requests.storage': '200Gi',
            'services': '20',
            'configmaps': '100',
            'secrets': '100',
        },
        'limits': {
            'default_request': {'cpu': '250m', 'memory': '256Mi'},
            'default': {'cpu': '1', 'memory': '1Gi'},
        },
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
    },
    'extra_large': {
        'version': 2,
        'quota': {
            'requests.cpu': '8',
            'limits.cpu': '16',
            'requests.memory': '16Gi',
            'limits.memory': '32Gi',
            'pods': '80',
            'persistentvolumeclaims': '40',
            'requests.storage': '400Gi',
            'services': '40',
            'configmaps': '200',
            'secrets': '200',
        },
        'limits': {
            'default_request': {'cpu': '500m', 'memory': '512Mi'},
            'default': {'cpu': '2', 'memory': '2Gi'},
        },
        'storage_policy': {'min': '1Gi', 'max': '10Gi'},
    },
}

_PROFILE_QUOTA_FIELDS = {
    'requests_cpu': 'requests.cpu',
    'limits_cpu': 'limits.cpu',
    'requests_memory': 'requests.memory',
    'limits_memory': 'limits.memory',
    'pods': 'pods',
    'persistentvolumeclaims': 'persistentvolumeclaims',
    'requests_storage': 'requests.storage',
    'services': 'services',
    'configmaps': 'configmaps',
    'secrets': 'secrets',
}
_PROFILE_LIMIT_FIELDS = {
    'default_cpu': ('default', 'cpu'),
    'default_memory': ('default', 'memory'),
    'default_request_cpu': ('default_request', 'cpu'),
    'default_request_memory': ('default_request', 'memory'),
}
_PROFILE_STORAGE_FIELDS = {
    'pvc_min_storage': 'min',
    'pvc_max_storage': 'max',
}
_CONTROL_TRUE_VALUES = {'1', 'true', 'yes', 'on'}

RESOURCE_PROFILE_ADVANCED_CONTROLS: dict[str, dict[str, Any]] = {
    'ingress': {
        'label': 'Ingress',
        'description': 'Govern Ingress exposure through the canonical Tenant exposure policy.',
        'authority': '#119',
        'providers': {
            'native_kubernetes': ('service_exposure_preflight', 'admission_enforcement'),
            'capsule': ('resource_rules', 'admission_enforcement'),
        },
    },
    'service_exposure': {
        'label': 'Service Exposure',
        'description': 'Govern ClusterIP, NodePort, LoadBalancer, and ExternalName exposure policy.',
        'authority': '#119',
        'providers': {
            'native_kubernetes': ('service_exposure_preflight', 'admission_enforcement'),
            'capsule': ('resource_rules', 'admission_enforcement'),
        },
    },
    'hostname_reservation': {
        'label': 'Hostname Reservation',
        'description': 'Require canonical hostname ownership and collision checks before exposure.',
        'authority': '#119',
        'providers': {
            'native_kubernetes': ('domain_policy_preflight', 'admission_enforcement'),
            'capsule': ('resource_rules', 'admission_enforcement'),
        },
    },
    'managed_tls': {
        'label': 'Managed TLS',
        'description': 'Request the canonical managed TLS capability for the attached placement.',
        'authority': '#118',
        'providers': {
            'native_kubernetes': ('managed_tls',),
            'capsule': ('replication',),
        },
    },
    'managed_registry': {
        'label': 'Managed Registry',
        'description': 'Request managed private-registry credential capability for the placement.',
        'authority': '#118',
        'providers': {
            'native_kubernetes': ('managed_registry',),
            'capsule': ('replication',),
        },
    },
    'capsule_namespace_controls': {
        'label': 'Capsule Namespace Controls',
        'description': 'Request Capsule namespace count/naming and related Tenant namespace controls.',
        'authority': '#121/#124',
        'providers': {
            'capsule': ('namespace_controls',),
        },
    },
    'capsule_resource_rules': {
        'label': 'Capsule Resource Rules',
        'description': 'Request Capsule StorageClass, PriorityClass, registry, ingress, and service rules.',
        'authority': '#121/#124',
        'providers': {
            'capsule': ('resource_rules',),
        },
    },
    'capsule_resource_pools': {
        'label': 'Capsule Resource Pools',
        'description': 'Request Capsule ResourcePool and claim capability.',
        'authority': '#124',
        'providers': {
            'capsule': ('resource_pools',),
        },
    },
    'capsule_replication': {
        'label': 'Capsule Replication',
        'description': 'Request TenantResource / GlobalTenantResource replication capability.',
        'authority': '#124',
        'providers': {
            'capsule': ('replication',),
        },
    },
    'capsule_tenant_cordon': {
        'label': 'Capsule Tenant Cordon',
        'description': 'Request Capsule Tenant/namespace cordon capability.',
        'authority': '#124',
        'providers': {
            'capsule': ('tenant_cordon',),
        },
    },
}


def _text(source: Mapping[str, Any], key: str) -> str:
    return str(source.get(key) or '').strip()
