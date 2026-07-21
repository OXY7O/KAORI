"""Canonical readiness composition for provider sources and scope bindings."""

from __future__ import annotations

from typing import Any, TypedDict


_READY = "ready"


class OperationalPosture(TypedDict):
    status: str
    label: str
    message: str


def resolve_binding_operational_status(
    *,
    source_readiness: str | None,
    binding_validation: str | None,
    source_enabled: bool = True,
    binding_enabled: bool = True,
) -> OperationalPosture:
    """Combine source readiness and binding validation without mutating persistence.

    Full Validation owns source readiness. Validate Binding owns binding
    validation. The source is the upstream gate, so its failure state takes
    precedence over the scope binding state.
    """
    source = (source_readiness or "validation_required").strip().lower()
    binding = (binding_validation or "validation_required").strip().lower()

    if not source_enabled:
        return {
            "status": "not_configured",
            "label": "Source Disabled",
            "message": "Enable the source before this scope can use it.",
        }
    if not binding_enabled:
        return {
            "status": "not_configured",
            "label": "Binding Disabled",
            "message": "Enable the binding before this operational scope can use the source.",
        }
    if source == "blocked":
        return {
            "status": "blocked",
            "label": "Source Blocked",
            "message": "Source readiness blocks operational use for every bound scope.",
        }
    if source == "degraded":
        return {
            "status": "degraded",
            "label": "Source Degraded",
            "message": "The source is reachable but requires attention before reliable operational use.",
        }
    if source != _READY:
        return {
            "status": "validation_required",
            "label": "Source Validation Required",
            "message": "Run Full Validation to establish source readiness.",
        }
    if binding == "blocked":
        return {
            "status": "blocked",
            "label": "Binding Blocked",
            "message": "Binding validation failed for this operational scope.",
        }
    if binding == "degraded":
        return {
            "status": "degraded",
            "label": "Binding Degraded",
            "message": "The binding is usable with incomplete or unexpected scope evidence.",
        }
    if binding != _READY:
        return {
            "status": "validation_required",
            "label": "Binding Validation Required",
            "message": "Run Validate Binding to prove the selector and scope contract.",
        }
    return {
        "status": "ready",
        "label": "Ready",
        "message": "Source readiness and binding validation are both Ready.",
    }


def resolve_cluster_coverage(
    *,
    kubernetes_readiness: str | None,
    source: Any | None,
    binding: Any | None,
) -> OperationalPosture:
    """Resolve one downstream consumer gate for a Kubernetes cluster."""
    kubernetes = (kubernetes_readiness or "validation_required").strip().lower()
    if kubernetes != _READY:
        if kubernetes == "blocked":
            return {
                "status": "blocked",
                "label": "Kubernetes Blocked",
                "message": "Kubernetes API readiness blocks this downstream consumer.",
            }
        if kubernetes == "degraded":
            return {
                "status": "degraded",
                "label": "Kubernetes Degraded",
                "message": "Kubernetes API readiness requires attention before this consumer is operational.",
            }
        return {
            "status": "validation_required",
            "label": "Kubernetes Validation Required",
            "message": "Run Kubernetes Full Validation before enabling downstream consumers.",
        }
    if source is None or binding is None:
        return {
            "status": "not_configured",
            "label": "Not Configured",
            "message": "Register or select a source and bind it to this Kubernetes cluster.",
        }
    return resolve_binding_operational_status(
        source_readiness=getattr(source, "readiness_status", None),
        binding_validation=getattr(binding, "validation_status", None),
        source_enabled=bool(getattr(source, "enabled", True)),
        binding_enabled=bool(getattr(binding, "enabled", True)),
    )
