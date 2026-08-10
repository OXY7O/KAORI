from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from kubernetes.client import (
    ApiClient,
    AuthorizationV1Api,
    V1ResourceAttributes,
    V1SelfSubjectAccessReview,
    V1SelfSubjectAccessReviewSpec,
)
from kubernetes.client.rest import ApiException

KUBERNETES_API_PROFILE = 'kubernetes-api-v1'


@dataclass(frozen=True)
class ApiCandidate:
    group: str
    version: str
    resource: str
    stability: str = 'stable'

    @property
    def api_version(self) -> str:
        return self.version if not self.group else f'{self.group}/{self.version}'

    @property
    def discovery_path(self) -> str:
        if not self.group:
            return f'/api/{self.version}'
        return f'/apis/{self.group}/{self.version}'

    @property
    def collection_path(self) -> str:
        if not self.group:
            return f'/api/{self.version}/{self.resource}'
        return f'/apis/{self.group}/{self.version}/{self.resource}'


@dataclass(frozen=True)
class FeatureContract:
    key: str
    candidates: tuple[ApiCandidate, ...]
    required_verbs: tuple[str, ...] = ('get', 'list')
    required: bool = True


FEATURE_CONTRACTS: tuple[FeatureContract, ...] = (
    FeatureContract('inventory.nodes', (ApiCandidate('', 'v1', 'nodes'),)),
    FeatureContract('inventory.namespaces', (ApiCandidate('', 'v1', 'namespaces'),)),
    FeatureContract('inventory.pods', (ApiCandidate('', 'v1', 'pods'),)),
    FeatureContract('inventory.services', (ApiCandidate('', 'v1', 'services'),)),
    FeatureContract('inventory.configmaps', (ApiCandidate('', 'v1', 'configmaps'),)),
    FeatureContract('inventory.secrets', (ApiCandidate('', 'v1', 'secrets'),), required=False),
    FeatureContract('inventory.resourcequotas', (ApiCandidate('', 'v1', 'resourcequotas'),)),
    FeatureContract('inventory.deployments', (ApiCandidate('apps', 'v1', 'deployments'),)),
    FeatureContract('inventory.statefulsets', (ApiCandidate('apps', 'v1', 'statefulsets'),)),
    FeatureContract('inventory.daemonsets', (ApiCandidate('apps', 'v1', 'daemonsets'),)),
    FeatureContract('inventory.jobs', (ApiCandidate('batch', 'v1', 'jobs'),)),
    FeatureContract(
        'inventory.cronjobs',
        (
            ApiCandidate('batch', 'v1', 'cronjobs'),
            ApiCandidate('batch', 'v1beta1', 'cronjobs', 'legacy'),
        ),
    ),
    FeatureContract(
        'inventory.ingresses',
        (
            ApiCandidate('networking.k8s.io', 'v1', 'ingresses'),
            ApiCandidate('networking.k8s.io', 'v1beta1', 'ingresses', 'legacy'),
            ApiCandidate('extensions', 'v1beta1', 'ingresses', 'legacy'),
        ),
    ),
    FeatureContract('inventory.storageclasses', (ApiCandidate('storage.k8s.io', 'v1', 'storageclasses'),)),
)


class KubernetesDiscovery:
    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client
        self._resource_cache: dict[str, dict[str, set[str]]] = {}

    def discover(self) -> dict[str, Any]:
        features: dict[str, dict[str, Any]] = {}
        selected_adapters: dict[str, dict[str, str]] = {}

        for contract in FEATURE_CONTRACTS:
            result = self._evaluate_contract(contract)
            features[contract.key] = result
            selected = result.get('selected_api')
            if selected:
                selected_adapters[contract.key] = selected

        required = [value for key, value in features.items() if self._contract(key).required]
        blocked = [value for value in required if value['status'] == 'blocked']
        legacy = [value for value in required if value['status'] == 'legacy']
        optional_blocked = [
            key for key, value in features.items() if not self._contract(key).required and value['status'] == 'blocked'
        ]
        optional_legacy = [
            key for key, value in features.items() if not self._contract(key).required and value['status'] == 'legacy'
        ]

        if blocked:
            compatibility_status = 'capability_mismatch'
            readiness_status = 'degraded'
        elif legacy:
            compatibility_status = 'compatible_with_warnings'
            readiness_status = 'degraded'
        else:
            compatibility_status = 'compatible'
            readiness_status = 'ready'

        return {
            'api_profile': KUBERNETES_API_PROFILE,
            'compatibility_status': compatibility_status,
            'readiness_status': readiness_status,
            'features': features,
            'selected_adapters': selected_adapters,
            'blocked_features': sorted(
                key for key, value in features.items() if self._contract(key).required and value['status'] == 'blocked'
            ),
            'legacy_features': sorted(
                key for key, value in features.items() if self._contract(key).required and value['status'] == 'legacy'
            ),
            'optional_blocked_features': sorted(optional_blocked),
            'optional_legacy_features': sorted(optional_legacy),
        }

    def _evaluate_contract(self, contract: FeatureContract) -> dict[str, Any]:
        observed: list[dict[str, Any]] = []
        for candidate in contract.candidates:
            resources = self._resources(candidate)
            verbs = resources.get(candidate.resource)
            if verbs is None:
                observed.append({'api_version': candidate.api_version, 'served': False})
                continue

            missing_verbs = sorted(set(contract.required_verbs) - verbs)
            denied_verbs = [verb for verb in contract.required_verbs if not self._can_i(candidate, verb)]
            observed.append(
                {
                    'api_version': candidate.api_version,
                    'served': True,
                    'verbs': sorted(verbs),
                    'missing_verbs': missing_verbs,
                    'denied_verbs': denied_verbs,
                    'stability': candidate.stability,
                }
            )
            if missing_verbs or denied_verbs:
                # A served stable API with insufficient authorization is a capability
                # failure, not a reason to try an older API and bypass the intended RBAC.
                return {
                    'status': 'blocked',
                    'required': contract.required,
                    'required_verbs': list(contract.required_verbs),
                    'selected_api': None,
                    'observed': observed,
                    'message': 'The API is served, but the kubeconfig lacks required access: '
                    + ', '.join(denied_verbs or missing_verbs),
                }

            status = 'legacy' if candidate.stability == 'legacy' else 'ready'
            return {
                'status': status,
                'required': contract.required,
                'required_verbs': list(contract.required_verbs),
                'selected_api': {
                    'group': candidate.group,
                    'version': candidate.version,
                    'resource': candidate.resource,
                    'stability': candidate.stability,
                },
                'observed': observed,
                'message': (
                    f'Using tested legacy API {candidate.api_version}.'
                    if status == 'legacy'
                    else f'Using stable API {candidate.api_version}.'
                ),
            }

        return {
            'status': 'blocked',
            'required': contract.required,
            'required_verbs': list(contract.required_verbs),
            'selected_api': None,
            'observed': observed,
            'message': 'No supported API candidate with the required verbs is available.',
        }

    def _can_i(self, candidate: ApiCandidate, verb: str) -> bool:
        review = V1SelfSubjectAccessReview(
            spec=V1SelfSubjectAccessReviewSpec(
                resource_attributes=V1ResourceAttributes(
                    group=candidate.group or '',
                    resource=candidate.resource,
                    verb=verb,
                )
            )
        )
        try:
            response = AuthorizationV1Api(self.api_client).create_self_subject_access_review(review)
        except ApiException as exc:
            # If authorization review itself is unavailable, actual inventory calls remain
            # authoritative. Do not falsely block the feature at discovery time.
            if exc.status in {403, 404}:
                return True
            raise
        return bool(getattr(getattr(response, 'status', None), 'allowed', False))

    def _resources(self, candidate: ApiCandidate) -> dict[str, set[str]]:
        path = candidate.discovery_path
        if path in self._resource_cache:
            return self._resource_cache[path]

        try:
            payload = self.api_client.call_api(
                path,
                'GET',
                response_types_map={200: 'object'},
                auth_settings=['BearerToken'],
                _return_http_data_only=True,
            )
        except ApiException as exc:
            if exc.status in {403, 404}:
                self._resource_cache[path] = {}
                return {}
            raise

        resources: dict[str, set[str]] = {}
        for item in _items(payload, 'resources'):
            name = _value(item, 'name')
            if not name or '/' in name:
                continue
            resources[str(name)] = set(_value(item, 'verbs', default=[]) or [])
        self._resource_cache[path] = resources
        return resources

    @staticmethod
    def _contract(key: str) -> FeatureContract:
        return next(item for item in FEATURE_CONTRACTS if item.key == key)


def list_cluster_resource(api_client: ApiClient, adapter: dict[str, str]) -> list[Any]:
    candidate = ApiCandidate(
        group=adapter.get('group', ''),
        version=adapter['version'],
        resource=adapter['resource'],
        stability=adapter.get('stability', 'stable'),
    )
    payload = api_client.call_api(
        candidate.collection_path,
        'GET',
        response_types_map={200: 'object'},
        auth_settings=['BearerToken'],
        _return_http_data_only=True,
    )
    return list(_items(payload, 'items'))


def _items(payload: Any, key: str) -> Iterable[Any]:
    value = _value(payload, key, default=[])
    return value or []


def _value(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)
