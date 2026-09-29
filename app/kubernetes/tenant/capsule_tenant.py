from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Any

from kubernetes.client import V1DeleteOptions
from kubernetes.client.rest import ApiException

from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.kubernetes.tenant.capsule_provider import CapsuleTenantProvider, discover_capsule
from app.kubernetes.tenant.providers import TenantProviderState
from app.models import Cluster

_CAPSULE_GROUP = 'capsule.clastix.io'
_CAPSULE_PLURAL = 'tenants'
_SUPPORTED_VERSIONS = ('v1beta2', 'v1beta1')
_MANAGED_BY_KEY = 'app.kubernetes.io/managed-by'
_MANAGED_BY_VALUE = 'kaori'
_TENANT_ID_KEY = 'kaori.io/tenant-id'
_TENANT_GENERATION_KEY = 'kaori.io/tenant-generation'
_ALLOWED_OWNER_KINDS = frozenset({'User', 'Group', 'ServiceAccount'})


@dataclass(frozen=True, slots=True)
class CapsuleTenantCreateResult:
    api_version: str
    provider_state: str
    provider_reference: str
    provider_uid: str | None
    resource_version: str | None
    owner_kind: str
    owner_name: str
    discovery_evidence: dict[str, object]

    def evidence(self) -> dict[str, object]:
        return {
            'provider': 'capsule',
            'source': 'tenant_setup_direct_create',
            'provider_api_version': self.api_version,
            'provider_reference': self.provider_reference,
            'provider_uid': self.provider_uid,
            'resource_version': self.resource_version,
            'owner': {
                'kind': self.owner_kind,
                'name': self.owner_name,
            },
            'capsule': self.discovery_evidence,
            'created_by_kaori': True,
            'provider_mutation_performed': True,
            'secret_material_persisted': False,
        }


def _read_or_none(api, *, version: str, name: str) -> dict[str, Any] | None:
    try:
        item = api.get_cluster_custom_object(
            _CAPSULE_GROUP,
            version,
            _CAPSULE_PLURAL,
            name,
            _request_timeout=5,
        )
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise
    return item if isinstance(item, dict) else None


def _select_version(snapshot) -> str:
    served = set(snapshot.tenant_api_versions)
    for version in _SUPPORTED_VERSIONS:
        if version in served:
            return version
    raise ValueError('Capsule Tenant creation requires a served capsule.clastix.io/v1beta2 or v1beta1 Tenant API.')


def _owner(kind: str, name: str) -> tuple[str, str]:
    normalized_kind = str(kind or '').strip()
    normalized_name = str(name or '').strip()
    if normalized_kind not in _ALLOWED_OWNER_KINDS:
        raise ValueError('Select a Capsule owner kind: User, Group, or ServiceAccount.')
    if not normalized_name or len(normalized_name) > 253:
        raise ValueError('Capsule owner subject is required and must be at most 253 characters.')
    return normalized_kind, normalized_name


def _body(
    *,
    api_version: str,
    tenant_name: str,
    kaori_tenant_id: str,
    generation: int,
    owner_kind: str,
    owner_name: str,
) -> dict[str, object]:
    return {
        'apiVersion': f'{_CAPSULE_GROUP}/{api_version}',
        'kind': 'Tenant',
        'metadata': {
            'name': tenant_name,
            'labels': {
                _MANAGED_BY_KEY: _MANAGED_BY_VALUE,
                _TENANT_ID_KEY: kaori_tenant_id,
                _TENANT_GENERATION_KEY: str(generation),
            },
        },
        'spec': {
            'owners': [
                {
                    'kind': owner_kind,
                    'name': owner_name,
                }
            ]
        },
    }


def create_capsule_tenant(
    *,
    cluster: Cluster,
    tenant_name: str,
    kaori_tenant_id: str,
    generation: int,
    owner_kind: str,
    owner_name: str,
) -> CapsuleTenantCreateResult:
    """Create the authoritative Capsule Tenant CR after a fail-closed live preflight."""

    owner_kind, owner_name = _owner(owner_kind, owner_name)
    client = runtime_adapter.build_client(cluster)
    api = client.custom_objects_api()

    try:
        initial = discover_capsule(api.api_client)
        version = _select_version(initial)
        if _read_or_none(api, version=version, name=tenant_name) is not None:
            raise ValueError(
                'A Capsule Tenant with this name already exists on the selected cluster. '
                'Use Tenant Discovery → Adoption instead of overwriting provider ownership.'
            )

        body = _body(
            api_version=version,
            tenant_name=tenant_name,
            kaori_tenant_id=kaori_tenant_id,
            generation=generation,
            owner_kind=owner_kind,
            owner_name=owner_name,
        )

        # Server-side dry-run proves the selected CRD/schema/admission path can
        # accept this exact Tenant without persisting a provider object.
        api.create_cluster_custom_object(
            _CAPSULE_GROUP,
            version,
            _CAPSULE_PLURAL,
            body,
            dry_run='All',
            _request_timeout=5,
        )

        qualified = discover_capsule(
            api.api_client,
            probes={'admission_enforcement': True},
        )
        provider = CapsuleTenantProvider(snapshot=qualified)
        binding = provider.validate_binding(cluster_id=str(cluster.id))
        if binding.state is not TenantProviderState.CAPSULE:
            raise ValueError(
                'Capsule Tenant creation is fail-closed because the controller/admission capability is degraded.'
            )

        created = api.create_cluster_custom_object(
            _CAPSULE_GROUP,
            version,
            _CAPSULE_PLURAL,
            body,
            _request_timeout=5,
        )
    except ValueError:
        raise
    except ApiException as exc:
        if exc.status == 409:
            raise ValueError(
                'A Capsule Tenant with this name already exists. Use Tenant Discovery → Adoption.'
            ) from exc
        raise ValueError(f'Capsule Tenant provider rejected direct creation: {str(exc)[:700]}') from exc
    except Exception as exc:
        raise ValueError(f'Capsule Tenant capability preflight failed: {str(exc)[:700]}') from exc

    metadata = created.get('metadata') if isinstance(created, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    return CapsuleTenantCreateResult(
        api_version=version,
        provider_state=TenantProviderState.CAPSULE.value,
        provider_reference=tenant_name,
        provider_uid=str(metadata.get('uid') or '') or None,
        resource_version=str(metadata.get('resourceVersion') or '') or None,
        owner_kind=owner_kind,
        owner_name=owner_name,
        discovery_evidence=qualified.as_dict(),
    )


def compensate_capsule_tenant_create(
    *,
    cluster: Cluster,
    api_version: str,
    tenant_name: str,
    kaori_tenant_id: str,
    expected_uid: str | None,
) -> bool:
    """Best-effort cleanup for a just-created KAORI-owned Capsule Tenant.

    The cleanup refuses to touch a different or foreign provider object.
    """

    client = runtime_adapter.build_client(cluster)
    api = client.custom_objects_api()
    try:
        current = _read_or_none(api, version=api_version, name=tenant_name)
        if current is None:
            return True
        metadata = current.get('metadata') if isinstance(current, dict) else {}
        metadata = metadata if isinstance(metadata, dict) else {}
        labels = metadata.get('labels') if isinstance(metadata, dict) else {}
        labels = labels if isinstance(labels, dict) else {}
        current_uid = str(metadata.get('uid') or '') or None
        if labels.get(_MANAGED_BY_KEY) != _MANAGED_BY_VALUE or labels.get(_TENANT_ID_KEY) != kaori_tenant_id:
            return False
        if expected_uid and current_uid and current_uid != expected_uid:
            return False
        api.delete_cluster_custom_object(
            _CAPSULE_GROUP,
            api_version,
            _CAPSULE_PLURAL,
            tenant_name,
            body=V1DeleteOptions(),
            _request_timeout=5,
        )
        return True
    except ApiException as exc:
        return exc.status == 404
    except Exception:
        return False


def delete_capsule_tenant_verified(
    *,
    cluster: Cluster,
    api_version: str,
    tenant_name: str,
    kaori_tenant_id: str,
    generation: int,
    expected_uid: str | None,
) -> dict[str, object]:
    """Delete one KAORI-created Capsule Tenant and verify provider absence.

    The adapter refuses foreign/adopted/replaced provider objects and never
    falls back to direct Native Kubernetes teardown.
    """

    client = runtime_adapter.build_client(cluster)
    api = client.custom_objects_api()

    try:
        snapshot = discover_capsule(api.api_client)
        if api_version not in snapshot.tenant_api_versions:
            raise ValueError(
                'Capsule Tenant API is unavailable or no longer serves the committed API version; '
                'provider absence cannot be verified safely.'
            )

        current = _read_or_none(api, version=api_version, name=tenant_name)
        if current is None:
            return {
                'provider': 'capsule',
                'operation': 'delete_tenant',
                'provider_reference': tenant_name,
                'provider_api_version': api_version,
                'provider_uid': expected_uid,
                'provider_verified_absent': True,
                'already_absent': True,
                'secret_material_persisted': False,
            }

        metadata = current.get('metadata') if isinstance(current, dict) else {}
        metadata = metadata if isinstance(metadata, dict) else {}
        labels = metadata.get('labels') if isinstance(metadata, dict) else {}
        labels = labels if isinstance(labels, dict) else {}
        current_uid = str(metadata.get('uid') or '') or None

        if labels.get(_MANAGED_BY_KEY) != _MANAGED_BY_VALUE:
            raise ValueError('Capsule Tenant is not KAORI-managed; provider deletion fails closed.')
        if labels.get(_TENANT_ID_KEY) != kaori_tenant_id:
            raise ValueError('Capsule Tenant ownership label does not match committed KAORI Tenant identity.')
        if str(labels.get(_TENANT_GENERATION_KEY) or '') != str(generation):
            raise ValueError('Capsule Tenant generation no longer matches committed KAORI intent.')
        if expected_uid and current_uid and current_uid != expected_uid:
            raise ValueError('Capsule Tenant UID changed; refusing to delete a replaced provider object.')

        try:
            api.delete_cluster_custom_object(
                _CAPSULE_GROUP,
                api_version,
                _CAPSULE_PLURAL,
                tenant_name,
                body=V1DeleteOptions(propagation_policy='Foreground'),
                _request_timeout=5,
            )
        except ApiException as exc:
            if exc.status != 404:
                raise

        for _ in range(10):
            if _read_or_none(api, version=api_version, name=tenant_name) is None:
                return {
                    'provider': 'capsule',
                    'operation': 'delete_tenant',
                    'provider_reference': tenant_name,
                    'provider_api_version': api_version,
                    'provider_uid': current_uid or expected_uid,
                    'provider_verified_absent': True,
                    'already_absent': False,
                    'secret_material_persisted': False,
                }
            sleep(0.5)

        raise ValueError('Capsule Tenant deletion was requested, but provider absence was not verified before timeout.')
    except ValueError:
        raise
    except ApiException as exc:
        raise ValueError(f'Capsule Tenant teardown failed closed: {str(exc)[:700]}') from exc
    except Exception as exc:
        raise ValueError(f'Capsule Tenant teardown verification failed: {str(exc)[:700]}') from exc
