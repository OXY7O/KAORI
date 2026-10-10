from __future__ import annotations

from types import SimpleNamespace

from jinja2 import Environment

from app.kubernetes.tenant.allocation_overview import (
    _partition_tenant_contributions,
    build_tenant_allocation_bars,
)


def _summary(*, cpu_budget: str | None = "10", cpu_used: str | None = "6") -> dict:
    return {
        "budget": {
            "available": {
                "cpu": cpu_budget,
                "memory_bytes": str(20 * 1024**3),
                "pods": "100",
                "storage_bytes": None,
            }
        },
        "committed": {
            "cpu": cpu_used,
            "memory_bytes": str(8 * 1024**3),
            "pods": "24",
            "storage_bytes": str(10 * 1024**3),
        },
        "display": {
            "budget": {"cpu": "10.00 cores", "memory": "20.00 GiB", "pods": "100 pods", "storage": "Not Governed"},
            "committed": {"cpu": "6.00 cores", "memory": "8.00 GiB", "pods": "24 pods", "storage": "10.00 GiB"},
            "headroom": {"cpu": "4.00 cores", "memory": "12.00 GiB", "pods": "76 pods", "storage": "Not Governed"},
        },
    }


def _namespace(tenant_id: str, name: str, *, cpu: str = "1") -> SimpleNamespace:
    return SimpleNamespace(
        namespace=name,
        environment=SimpleNamespace(tenant_id=tenant_id, environment="development"),
        allocation_quota_json={
            "requests.cpu": cpu,
            "requests.memory": "1Gi",
            "pods": "5",
            "requests.storage": "2Gi",
        },
        provisioning_status="ready",
    )


def test_budget_composition_uses_committed_governance_values_not_utilization() -> None:
    bars = build_tenant_allocation_bars(_summary())
    assert [bar["key"] for bar in bars] == ["cpu", "memory_bytes", "pods", "storage_bytes"]
    assert bars[0]["known"] is True
    assert bars[0]["percent"] == "60.0"
    assert bars[0]["free_percent"] == "40.0"
    assert bars[1]["percent"] == "40.0"
    assert bars[2]["percent"] == "24.0"
    assert bars[3]["known"] is False
    assert bars[3]["state"] == "Not Governed"


def test_unknown_and_overcommitted_budget_does_not_claim_free_capacity() -> None:
    unknown = build_tenant_allocation_bars(_summary(cpu_budget=None))[0]
    assert unknown["known"] is False
    assert unknown["state"] == "Unknown"

    over = build_tenant_allocation_bars(_summary(cpu_budget="5", cpu_used="6"))[0]
    assert over["known"] is True
    assert over["percent"] == "100.0"
    assert over["free_percent"] == "0.0"
    assert over["state"] == "Overcommitted"
    assert over["shortfall"] == "1.00 cores"

    zero = build_tenant_allocation_bars(_summary(cpu_budget="0", cpu_used="0"))[0]
    assert zero["known"] is False
    assert zero["state"] == "Exhausted"


def test_created_and_adopted_tenants_share_one_canonical_ledger() -> None:
    created = SimpleNamespace(id="created", name="Created", provider_key="native_kubernetes", ownership_status="managed")
    adopted = SimpleNamespace(id="adopted", name="Adopted", provider_key="native_kubernetes", ownership_status="adopted")
    rows = _partition_tenant_contributions(
        [created, adopted],
        [_namespace("created", "created-ns", cpu="2"), _namespace("adopted", "adopted-ns", cpu="3")],
        {},
        [],
    )
    assert len(rows) == 2
    assert [r["allocation"]["cpu"] for r in rows] == ["2.00 cores", "3.00 cores"]
    assert [r["namespace_count"] for r in rows] == [1, 1]
    assert all(r["source"] == "Namespace Quotas" for r in rows)


def test_capsule_shared_tenant_quota_is_counted_once_not_per_namespace() -> None:
    capsule = SimpleNamespace(id="capsule", name="Capsule", provider_key="capsule", ownership_status="managed")
    rows = _partition_tenant_contributions(
        [capsule],
        [_namespace("capsule", "one"), _namespace("capsule", "two")],
        {"capsule": {"requests.cpu": "4", "requests.memory": "8Gi", "pods": "20", "requests.storage": "10Gi"}},
        [],
    )
    assert len(rows) == 1
    assert rows[0]["allocation"]["cpu"] == "4.00 cores"
    assert rows[0]["namespace_count"] == 2
    assert rows[0]["source"] == "Shared Tenant Quota"


def test_ambiguous_shared_quota_stays_unknown() -> None:
    capsule = SimpleNamespace(id="ambiguous", name="Ambiguous", provider_key="capsule", ownership_status="managed")
    rows = _partition_tenant_contributions([capsule], [_namespace("ambiguous", "one")], {}, ["ambiguous"])
    assert rows[0]["unknown"] is True
    assert rows[0]["source"] == "Ambiguous Shared Quota"
    assert rows[0]["allocation"]["cpu"] == "N/A"


def test_tenant_allocation_overview_template_parses_with_jinja() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    template = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    Environment(autoescape=True).parse(template)
    assert 'id="{{ overview_id }}"' in template
    assert "allocation_overview.bars" in template
    assert "row.namespaces" in template
    assert "registry_ui.footer" in template
    assert "analytics.capacity" in template
    assert "actual workload utilization" in template
