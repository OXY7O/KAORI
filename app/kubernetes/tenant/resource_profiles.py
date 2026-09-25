from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.kubernetes.tenant.validation import validate_profile_spec

RESOURCE_PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    'small': {
        'label': 'Small',
        'description': 'Development and low-footprint workloads.',
        'quota_hard': {
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
        'limit_defaults': {
            'default': {'cpu': '250m', 'memory': '256Mi'},
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
        },
    },
    'standard': {
        'label': 'Standard',
        'description': 'General-purpose tenant baseline.',
        'quota_hard': {
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
        'limit_defaults': {
            'default': {'cpu': '500m', 'memory': '512Mi'},
            'default_request': {'cpu': '100m', 'memory': '128Mi'},
        },
    },
    'large': {
        'label': 'Large',
        'description': 'Higher-capacity tenant baseline.',
        'quota_hard': {
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
        'limit_defaults': {
            'default': {'cpu': '1000m', 'memory': '1Gi'},
            'default_request': {'cpu': '250m', 'memory': '256Mi'},
        },
    },
}

_QUOTA_FORM_FIELDS = {
    'requests.cpu': 'requests_cpu',
    'limits.cpu': 'limits_cpu',
    'requests.memory': 'requests_memory',
    'limits.memory': 'limits_memory',
    'pods': 'pods',
    'persistentvolumeclaims': 'persistentvolumeclaims',
    'requests.storage': 'requests_storage',
    'services': 'services',
    'configmaps': 'configmaps',
    'secrets': 'secrets',
}

_LIMIT_FORM_FIELDS = {
    ('default_request', 'cpu'): 'default_request_cpu',
    ('default', 'cpu'): 'default_cpu',
    ('default_request', 'memory'): 'default_request_memory',
    ('default', 'memory'): 'default_memory',
}


def resolve_resource_profile_spec(profile_class: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    preset = RESOURCE_PROFILE_PRESETS.get(profile_class)
    if preset is None:
        raise ValueError('Selected Resource Profile class does not have a KAORI preset.')
    quota, limits = validate_profile_spec(preset['quota_hard'], preset['limit_defaults'])
    return deepcopy(quota), deepcopy(limits)


def preset_form_values() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for key, preset in RESOURCE_PROFILE_PRESETS.items():
        values: dict[str, str] = {}
        for quota_key, form_field in _QUOTA_FORM_FIELDS.items():
            values[form_field] = str(preset['quota_hard'][quota_key])
        for (group, resource), form_field in _LIMIT_FORM_FIELDS.items():
            values[form_field] = str(preset['limit_defaults'][group][resource])
        payload[key] = {
            'label': preset['label'],
            'description': preset['description'],
            'values': values,
        }
    return payload
