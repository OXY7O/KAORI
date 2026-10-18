from __future__ import annotations

from typing import Any

from sqlalchemy.orm import load_only

from app.extensions.db import db
from app.kubernetes.tenant.resource_profile_controls import namespace_allocation_is_current, namespace_allocation_values
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantResourceProfile,
)


def _resource_profile_rollout_targets(profile_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Present committed Native rollout readiness for the paginated profile set.

    Exact current-state comparison mirrors the Rollout service; no provider reads.
    """
    if not profile_ids:
        return {}

    profiles = {
        profile.id: profile
        for profile in TenantResourceProfile.query.filter(TenantResourceProfile.id.in_(profile_ids)).all()
    }
    desired_by_profile: dict[int, tuple[dict[str, str], dict[str, dict[str, str]], dict[str, str]] | None] = {}
    for profile_id, profile in profiles.items():
        try:
            quota, limits, storage, _ = namespace_allocation_values(profile)
        except ValueError:
            # Invalid committed profile data is never assumed current.
            desired_by_profile[profile_id] = None
        else:
            desired_by_profile[profile_id] = (quota, limits, storage)

    # One committed-state projection for the paginated (normally five) profiles;
    # avoid per-Tenant queries and avoid reaching any external provider.
    rows = (
        db.session.query(TenantNamespace, Tenant.id, Tenant.name, Tenant.provider_key, Tenant.lifecycle_status)
        .options(
            load_only(
                TenantNamespace.id,
                TenantNamespace.resource_profile_id,
                TenantNamespace.resource_profile_version,
                TenantNamespace.allocation_quota_json,
                TenantNamespace.allocation_limit_defaults_json,
                TenantNamespace.allocation_storage_policy_json,
            )
        )
        .join(TenantEnvironment, TenantEnvironment.id == TenantNamespace.tenant_environment_id)
        .join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(
            TenantNamespace.resource_profile_id.in_(profile_ids),
            TenantNamespace.provisioning_status.notin_(
                (
                    TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
                    TenantNamespaceProvisioningStatus.RELEASED.value,
                )
            ),
        )
        .order_by(Tenant.name.asc(), TenantNamespace.namespace.asc(), TenantNamespace.id.asc())
        .all()
    )

    result: dict[int, list[dict[str, Any]]] = {profile_id: [] for profile_id in profile_ids}
    targets: dict[tuple[int, str], dict[str, Any]] = {}
    for record, tenant_id, tenant_name, provider_key, lifecycle_status in rows:
        profile_id = record.resource_profile_id
        profile = profiles.get(profile_id) if profile_id is not None else None
        if profile is None:
            continue

        key = (profile.id, str(tenant_id))
        target = targets.get(key)
        if target is None:
            target = {
                'tenant_id': str(tenant_id),
                'tenant_name': str(tenant_name),
                'provider_key': str(provider_key),
                'eligible': (
                    provider_key == 'native_kubernetes'
                    and lifecycle_status == TenantLifecycleStatus.READY.value
                    and profile.enabled
                ),
                'namespaces': 0,
                'outdated': 0,
                'pending': 0,
                'already_current': False,
            }
            result[profile.id].append(target)
            targets[key] = target

        target['namespaces'] += 1
        if int(record.resource_profile_version or 0) != int(profile.version or 1):
            target['outdated'] += 1

        desired = desired_by_profile[profile.id]
        if desired is None or not namespace_allocation_is_current(record, profile, *desired):
            target['pending'] += 1

    for target in targets.values():
        # A version-only zero is insufficient. Require every committed snapshot
        # to match all three allocation families and the version.
        target['already_current'] = target['eligible'] and target['pending'] == 0 and target['namespaces'] > 0

    return result


