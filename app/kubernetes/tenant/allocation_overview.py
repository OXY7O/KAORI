"""Read-only Tenant logical allocation presentation from canonical committed evidence.

There is no provider read and no reimplementation of #654 admission arithmetic.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import joinedload

from app.kubernetes.tenant.capacity_allocation_state import (
    _aggregate_committed_allocation,
    _canonical_shared_allocation_quota,
)
from app.kubernetes.tenant.capacity import CapacityVector
from app.kubernetes.tenant.capacity_governance_support import _vector_display
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")

_DIMENSIONS = (
    ("cpu", "CPU Requests", "cpu", "Compute request commitment"),
    ("memory_bytes", "Memory Requests", "memory", "Compute request commitment"),
    ("pods", "Pod Slots", "pods", "Logical Pod quota commitment"),
    ("storage_bytes", "Logical Storage", "storage", "Explicit Tenant requests.storage budget; not backend free space"),
)


def _share(value: Decimal, total: Decimal) -> str:
    """A display percentage only; never used to make admission decisions."""
    return format(min(max(value * _HUNDRED / total, _ZERO), _HUNDRED).quantize(Decimal("0.1")), "f")


def build_tenant_allocation_bars(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Render canonical #654 budget/commitment/headroom; never substitute zero for unknown."""
    budget = summary.get("budget")
    available = budget.get("available") if isinstance(budget, Mapping) else None
    committed = summary.get("committed")
    displays = summary.get("display")
    budget_display = displays.get("budget") if isinstance(displays, Mapping) else None
    committed_display = displays.get("committed") if isinstance(displays, Mapping) else None
    headroom_display = displays.get("headroom") if isinstance(displays, Mapping) else None
    result: list[dict[str, Any]] = []
    for key, label, display_key, explanation in _DIMENSIONS:
        ceiling = available.get(key) if isinstance(available, Mapping) else None
        used = committed.get(key) if isinstance(committed, Mapping) else None
        record: dict[str, object] = {
            "key": key,
            "label": label,
            "explanation": explanation,
            "budget": budget_display.get(display_key, "N/A") if isinstance(budget_display, Mapping) else "N/A",
            "committed": committed_display.get(display_key, "N/A") if isinstance(committed_display, Mapping) else "N/A",
            "headroom": headroom_display.get(display_key, "N/A") if isinstance(headroom_display, Mapping) else "N/A",
            "known": False,
            "percent": "0",
            "free_percent": "0",
            "shortfall": None,
            "state": "Unknown" if key != "storage_bytes" else "Not Governed",
        }
        if ceiling is not None and used is not None:
            total = Decimal(str(ceiling))
            consumed = Decimal(str(used))
            if total > _ZERO and consumed >= _ZERO:
                bounded = min(consumed, total)
                record.update(
                    known=True,
                    percent=_share(bounded, total),
                    free_percent=_share(total - bounded, total),
                    state="Overcommitted" if consumed > total else "Governed",
                )
            elif total == _ZERO:
                record.update(state="Exhausted" if consumed == _ZERO else "Overcommitted")
            if consumed > total:
                shortfall = consumed - total
                # Canonical commitment units and display formatting remain #654-owned.
                values: dict[str, Decimal | None] = {dim[0]: None for dim in _DIMENSIONS}
                values[key] = shortfall
                record["shortfall"] = _vector_display(CapacityVector(
                    cpu=values["cpu"],
                    memory_bytes=values["memory_bytes"],
                    pods=values["pods"],
                    storage_bytes=values["storage_bytes"],
                ))[display_key]
        result.append(record)
    return result


def describe_tightest_headroom(
    bars: list[dict[str, Any]], state: str
) -> str | None:
    """Describe the tightest already-governed allocation dimension; never classify admission."""
    if state not in {"Near Capacity", "Critical", "Exhausted"}:
        return None
    governed = [bar for bar in bars if bar["known"] and bar["state"] == "Governed"]
    if not governed:
        return None
    tightest = min(governed, key=lambda bar: Decimal(str(bar["free_percent"])))
    return f"Lowest headroom: {tightest['label']} ({tightest['free_percent']}%)"


def filter_tenant_contribution_rows(
    rows: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """Filter committed Tenant evidence without modifying its canonical allocation."""
    needle = query.strip().casefold()
    if not needle:
        return rows
    return [
        row for row in rows
        if needle in str(row["tenant"].name).casefold()
        or needle in str(row["tenant"].id).casefold()
        or needle in str(row["source"]).casefold()
        or any(
            needle in str(namespace["name"]).casefold()
            or needle in str(namespace["environment"]).casefold()
            for namespace in row["namespaces"]
        )
    ]


def build_tenant_contribution_rows(cluster_id: str) -> list[dict[str, object]]:
    """Partition the same canonical ledger as #654, including shared-quota rules."""
    tenants = Tenant.query.filter_by(cluster_id=cluster_id).order_by(Tenant.name.asc(), Tenant.id.asc()).all()
    namespaces = (
        TenantNamespace.query.options(
            joinedload(TenantNamespace.environment).joinedload(TenantEnvironment.tenant),
        )
        .filter(
            TenantNamespace.cluster_id == cluster_id,
            TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value,
        )
        .order_by(TenantNamespace.namespace.asc())
        .all()
    )
    shared, ambiguous = _canonical_shared_allocation_quota(cluster_id)
    return _partition_tenant_contributions(tenants, namespaces, shared, ambiguous)


def _partition_tenant_contributions(
    tenants: list[Tenant],
    namespaces: list[TenantNamespace],
    shared: Mapping[str, Mapping[str, object]],
    ambiguous: list[str],
) -> list[dict[str, Any]]:
    """Pure read-model partition; match #654's shared and ambiguous accounting."""
    by_tenant: dict[str, list[TenantNamespace]] = defaultdict(list)
    for row in namespaces:
        by_tenant[str(row.environment.tenant_id)].append(row)

    results = []
    for tenant in tenants:
        rows = by_tenant.get(str(tenant.id), [])
        if not rows and str(tenant.id) not in shared and str(tenant.id) not in ambiguous:
            continue
        quota = {str(tenant.id): shared[str(tenant.id)]} if str(tenant.id) in shared else {}
        vector, unbounded = _aggregate_committed_allocation(
            rows,
            shared_quota_by_tenant=quota,
            ambiguous_shared_tenants=[str(tenant.id)] if str(tenant.id) in ambiguous else [],
        )
        results.append({
            "tenant": tenant,
            "namespace_count": len(rows),
            "allocation": _vector_display(vector),
            "unknown": bool(unbounded) or any(
                value is None for value in (vector.cpu, vector.memory_bytes, vector.pods, vector.storage_bytes)
            ),
            "source": "Shared Tenant Quota" if quota else "Ambiguous Shared Quota" if str(tenant.id) in ambiguous else "Namespace Quotas",
            "namespaces": [
                {
                    "name": row.namespace,
                    "environment": row.environment.environment,
                    "state": row.provisioning_status,
                }
                for row in rows
            ],
        })
    return results
