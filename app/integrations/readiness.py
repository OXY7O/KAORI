"""Presentation-safe readiness composition for provider sources and scope bindings."""

from __future__ import annotations

from typing import Any


_READY = "ready"


def resolve_binding_operational_status(
    *,
    source_readiness: str | None,
    binding_validation: str | None,
    source_enabled: bool = True,
    binding_enabled: bool = True,
) -> dict[str, str]:
    """Return a conservative operational status without mutating persisted readiness."""
    source = source_readiness or "validation_required"
    binding = binding_validation or "validation_required"

    if not source_enabled:
        return {"status": "disabled", "label": "Source Disabled"}
    if not binding_enabled:
        return {"status": "disabled", "label": "Binding Disabled"}
    if source == "blocked":
        return {"status": "blocked", "label": "Source Blocked"}
    if binding == "blocked":
        return {"status": "blocked", "label": "Binding Blocked"}
    if source == "degraded":
        return {"status": "degraded", "label": "Source Degraded"}
    if binding == "degraded":
        return {"status": "degraded", "label": "Binding Degraded"}
    if source != _READY:
        return {"status": "validation_required", "label": "Source Validation Required"}
    if binding != _READY:
        return {"status": "validation_required", "label": "Binding Validation Required"}
    return {"status": "ready", "label": "Ready"}


def resolve_cluster_coverage(
    *,
    kubernetes_readiness: str | None,
    source: Any | None,
    binding: Any | None,
) -> dict[str, str]:
    """Resolve one downstream domain gate for a Kubernetes cluster."""
    kubernetes = kubernetes_readiness or "validation_required"
    if kubernetes != _READY:
        if kubernetes == "blocked":
            return {"status": "blocked", "label": "Kubernetes Blocked"}
        if kubernetes == "degraded":
            return {"status": "degraded", "label": "Kubernetes Degraded"}
        return {
            "status": "validation_required",
            "label": "Kubernetes Validation Required",
        }
    if source is None or binding is None:
        return {"status": "not_configured", "label": "Not Configured"}
    return resolve_binding_operational_status(
        source_readiness=getattr(source, "readiness_status", None),
        binding_validation=getattr(binding, "validation_status", None),
        source_enabled=bool(getattr(source, "enabled", True)),
        binding_enabled=bool(getattr(binding, "enabled", True)),
    )
