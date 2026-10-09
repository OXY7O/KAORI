from __future__ import annotations

from copy import deepcopy

import pytest

from app.kubernetes.tenant.external_access_inventory import normalize_capsule_external_access


def _tenant():
    return {
        "metadata": {"name": "sandbox", "uid": "tenant-uid", "resourceVersion": "12"},
        "spec": {
            "owners": [{"kind": "User", "name": "alice"}, {"kind": "Group", "name": "engineering"}],
            "additionalRoleBindings": [{
                "clusterRoleName": "company-read-only",
                "subjects": [{"kind": "Group", "name": "platform"}],
            }],
            "rules": [{
                "namespaceSelector": {"matchLabels": {"team": "sandbox"}},
                "permissions": {
                    "bindings": [{
                        "clusterRoleName": "kaori-tenant-viewer-v1",
                        "subjects": [{"kind": "User", "name": "bob"}],
                        "labels": {
                            "app.kubernetes.io/managed-by": "kaori",
                            "kaori.io/access-grant": "grant-uid",
                        },
                    }]
                },
            }],
        },
    }


def test_capsule_external_rbac_observed_without_import_or_mutation():
    item = _tenant()
    original = deepcopy(item)
    row = normalize_capsule_external_access(tenant_name="sandbox", tenant_uid="tenant-uid", tenant_item=item)

    assert row["provider"] == "capsule"
    assert row["owners"] == [
        {"kind": "User", "name": "alice", "classification": "external_observed"},
        {"kind": "Group", "name": "engineering", "classification": "external_observed"},
    ]
    assert row["bindings"][0]["ownership"] == "external_observed"
    assert row["bindings"][0]["grant_correlation"] is None
    assert row["bindings"][1]["ownership"] == "kaori_marked"
    assert row["bindings"][1]["grant_correlation"] == "grant-uid"
    assert row["bindings"][1]["namespace_selector"] == {"matchLabels": {"team": "sandbox"}}
    assert row["identity_imported"] is False
    assert row["grant_imported"] is False
    assert row["provider_mutation_performed"] is False
    assert len(row["evidence_sha256"]) == 64
    assert item == original


@pytest.mark.parametrize(
    "mutation",
    [
        lambda obj: obj["metadata"].update(uid="replacement"),
        lambda obj: obj["spec"].update(owners=[{"kind": "Unsupported", "name": "bad"}]),
        lambda obj: obj["spec"].update(additionalRoleBindings=[{"clusterRoleName": "view"}]),
        lambda obj: obj["spec"]["rules"][0]["permissions"].update(bindings="invalid"),
        lambda obj: obj["spec"]["additionalRoleBindings"][0].update(
            subjects=[{"kind": "ServiceAccount", "name": "robot"}]
        ),
    ],
)
def test_capsule_external_access_fail_closed_on_unsupported_or_ambiguous_evidence(mutation):
    item = _tenant()
    mutation(item)
    with pytest.raises(ValueError):
        normalize_capsule_external_access(tenant_name="sandbox", tenant_uid="tenant-uid", tenant_item=item)


def test_capsule_external_access_hash_is_deterministic_and_changes_with_grants():
    item = _tenant()
    first = normalize_capsule_external_access(tenant_name="sandbox", tenant_uid="tenant-uid", tenant_item=item)
    again = normalize_capsule_external_access(tenant_name="sandbox", tenant_uid="tenant-uid", tenant_item=item)
    assert first["evidence_sha256"] == again["evidence_sha256"]

    item["spec"]["additionalRoleBindings"][0]["subjects"][0]["name"] = "security"
    changed = normalize_capsule_external_access(tenant_name="sandbox", tenant_uid="tenant-uid", tenant_item=item)
    assert changed["evidence_sha256"] != first["evidence_sha256"]
