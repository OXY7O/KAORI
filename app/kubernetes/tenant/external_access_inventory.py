"""Read-only normalization for externally provisioned Tenant access evidence.

No resource mutation, user creation, profile assignment, or grant import occurs here.
Kubernetes/Capsule remains authoritative for provider-native identity and RBAC.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

_MANAGED_BY = "app.kubernetes.io/managed-by"
_GRANT_LABEL = "kaori.io/access-grant"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _subject(item: Mapping[str, Any]) -> dict[str, str]:
    """Normalize subject identifiers only, never infer a KAORI User/IdP membership."""
    kind = _text(item.get("kind"))
    name = _text(item.get("name"))
    if kind not in {"User", "Group", "ServiceAccount"} or not name:
        raise ValueError("Unsupported or incomplete Kubernetes RBAC subject.")
    namespace = _text(item.get("namespace"))
    if kind == "ServiceAccount" and not namespace:
        raise ValueError("ServiceAccount subject has no explicit namespace.")
    return {
        "kind": kind,
        "name": name,
        "namespace": namespace if kind == "ServiceAccount" else "",
    }


def _provider_binding(entry: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    """Normalize an observed Capsule distribution binding without claiming authority."""
    labels = entry.get("labels") or {}
    if not isinstance(labels, Mapping):
        raise ValueError("Capsule RBAC binding labels are malformed.")
    role_name = _text(entry.get("clusterRoleName"))
    subjects = entry.get("subjects")
    if not role_name or not isinstance(subjects, list) or not subjects:
        raise ValueError("Capsule role binding has no role or valid subjects.")
    if not all(isinstance(subject, Mapping) for subject in subjects):
        raise ValueError("Capsule binding subject is malformed.")
    owned = _text(labels.get(_MANAGED_BY)) == "kaori" and bool(_text(labels.get(_GRANT_LABEL)))
    return {
        "source": source,
        "cluster_role": role_name,
        "subjects": [_subject(subject) for subject in subjects],
        "ownership": "kaori_marked" if owned else "external_observed",
        "grant_correlation": _text(labels.get(_GRANT_LABEL)) if owned else None,
        "managed_by": _text(labels.get(_MANAGED_BY)) or None,
    }


def normalize_capsule_external_access(
    *, tenant_name: str, tenant_uid: str, tenant_item: Mapping[str, Any]
) -> dict[str, Any]:
    """Snapshot Capsule owners and RBAC without importing or altering principals.

    The result is non-secret and can be committed as a provider observation.
    An owner is *never* inferred to be an active KAORI Tenant Membership.
    """
    metadata = tenant_item.get("metadata") or {}
    spec = tenant_item.get("spec") or {}
    if not isinstance(metadata, Mapping) or not isinstance(spec, Mapping):
        raise ValueError("Capsule Tenant identity/schema is malformed.")
    if _text(metadata.get("name")) != tenant_name or _text(metadata.get("uid")) != tenant_uid:
        raise ValueError("Capsule Tenant UID/name changed; refuse identity correlation.")
    owners = spec.get("owners") or []
    extra = spec.get("additionalRoleBindings") or []
    rules = spec.get("rules") or []
    if not isinstance(owners, list) or not isinstance(extra, list) or not isinstance(rules, list):
        raise ValueError("Capsule external RBAC contract is malformed.")

    observed_owners = []
    for owner in owners:
        if not isinstance(owner, Mapping):
            raise ValueError("Capsule owner entry is malformed.")
        kind = _text(owner.get("kind")) or "User"
        name = _text(owner.get("name"))
        if kind not in {"User", "Group", "ServiceAccount"} or not name:
            raise ValueError("Capsule owner principal is unsupported or incomplete.")
        observed_owners.append({"kind": kind, "name": name, "classification": "external_observed"})

    bindings = []
    for entry in extra:
        if not isinstance(entry, Mapping):
            raise ValueError("Capsule additionalRoleBindings entry is malformed.")
        bindings.append(_provider_binding(entry, source="capsule_tenant_wide"))
    for position, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            raise ValueError("Capsule scoped rule is malformed.")
        permissions = rule.get("permissions") or {}
        if not isinstance(permissions, Mapping):
            raise ValueError("Capsule scoped permissions are malformed.")
        items = permissions.get("bindings") or []
        if not isinstance(items, list):
            raise ValueError("Capsule scoped bindings are malformed.")
        selector = rule.get("namespaceSelector")
        for entry in items:
            if not isinstance(entry, Mapping):
                raise ValueError("Capsule scoped RBAC entry is malformed.")
            binding = _provider_binding(entry, source="capsule_namespace_selector")
            binding["rule_index"] = position
            # The raw selector is evidence, never a KAORI scope entitlement.
            binding["namespace_selector"] = selector if isinstance(selector, Mapping) else None
            bindings.append(binding)

    observed = {
        "provider": "capsule",
        "tenant_name": tenant_name,
        "tenant_uid": tenant_uid,
        "tenant_resource_version": _text(metadata.get("resourceVersion")),
        "owners": observed_owners,
        "bindings": bindings,
        "identity_imported": False,
        "grant_imported": False,
        "provider_mutation_performed": False,
        "secret_material_persisted": False,
    }
    # Canonical evidence hash for change detection; never a claim of managed ownership.
    observed["evidence_sha256"] = hashlib.sha256(
        json.dumps(observed, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return observed
