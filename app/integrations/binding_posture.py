"""Shared source and binding operational posture for integration presentation."""

from __future__ import annotations

from typing import TypedDict


class BindingOperationalPosture(TypedDict):
    status: str
    label: str
    message: str


def resolve_binding_operational_posture(
    *,
    source_readiness: str | None,
    binding_validation: str | None,
    source_enabled: bool = True,
    binding_enabled: bool = True,
) -> BindingOperationalPosture:
    """Combine provider readiness and scope validation without conflating them.

    Full Validation owns ``source_readiness``. Validate Binding owns
    ``binding_validation``. Operational Status is the conservative combination
    used by consumer resolution and the management UI.
    """
    if not source_enabled:
        return {
            'status': 'not_configured',
            'label': 'Source Disabled',
            'message': 'Enable the source before this binding can be used.',
        }
    if not binding_enabled:
        return {
            'status': 'not_configured',
            'label': 'Binding Disabled',
            'message': 'Enable the binding before this operational scope can use the source.',
        }

    binding_status = (binding_validation or 'validation_required').strip().lower()
    source_status = (source_readiness or 'validation_required').strip().lower()

    if binding_status == 'blocked':
        return {
            'status': 'blocked',
            'label': 'Binding Blocked',
            'message': 'Binding validation failed for this operational scope.',
        }
    if binding_status == 'degraded':
        return {
            'status': 'degraded',
            'label': 'Binding Degraded',
            'message': 'The binding is usable with incomplete or unexpected scope evidence.',
        }
    if binding_status not in {'ready'}:
        return {
            'status': 'validation_required',
            'label': 'Binding Validation Required',
            'message': 'Run Validate Binding to prove the selector and scope contract.',
        }

    if source_status == 'blocked':
        return {
            'status': 'blocked',
            'label': 'Source Blocked',
            'message': 'The binding is valid, but source readiness blocks operational use.',
        }
    if source_status == 'degraded':
        return {
            'status': 'degraded',
            'label': 'Source Degraded',
            'message': 'The binding is valid, but source readiness requires attention.',
        }
    if source_status != 'ready':
        return {
            'status': 'validation_required',
            'label': 'Source Validation Required',
            'message': 'Run Full Validation to establish source readiness.',
        }

    return {
        'status': 'ready',
        'label': 'Ready',
        'message': 'Source readiness and binding validation are both Ready.',
    }
