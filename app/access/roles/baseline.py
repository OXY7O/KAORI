from __future__ import annotations

from dataclasses import dataclass

from app.access.rbac.defaults import DEFAULT_ROLE_DEFINITIONS, DEFAULT_ROLE_PERMISSIONS
from app.access.rbac.policy import role_is_protected_default
from app.models import Role


@dataclass(frozen=True, slots=True)
class RoleBaselineState:
    key: str
    label: str
    tone: str
    icon: str
    detail: str


def _canonical_state(role: Role) -> RoleBaselineState:
    expected = DEFAULT_ROLE_DEFINITIONS[role.name]
    expected_permissions = DEFAULT_ROLE_PERMISSIONS.get(role.name, set())
    actual_permissions = role.permission_keys()
    findings: list[str] = []

    if not role.is_system:
        findings.append('system ownership flag differs from the code-owned baseline')
    if not role.is_active:
        findings.append('protected default is inactive')
    if role.display_name != expected['display_name']:
        findings.append('display name differs from the source-controlled definition')
    if (role.description or '') != (expected['description'] or ''):
        findings.append('description differs from the source-controlled definition')
    if actual_permissions != expected_permissions:
        missing = len(expected_permissions - actual_permissions)
        unexpected = len(actual_permissions - expected_permissions)
        findings.append(f'permission scope differs ({missing} missing, {unexpected} unexpected)')

    if findings:
        return RoleBaselineState(
            key='drift',
            label='Baseline Drift',
            tone='warning',
            icon='triangle-alert',
            detail='; '.join(findings) + '.',
        )
    return RoleBaselineState(
        key='canonical',
        label='Canonical',
        tone='normal',
        icon='circle-check',
        detail='Protected default matches the source-controlled role definition.',
    )


def role_baseline_state(role: Role) -> RoleBaselineState:
    if role_is_protected_default(role):
        return _canonical_state(role)
    if role.is_system:
        return RoleBaselineState(
            key='unexpected_system',
            label='Unexpected System Role',
            tone='warning',
            icon='database-zap',
            detail='Database marks this role as system-owned, but no source-controlled default defines it.',
        )
    return RoleBaselineState(
        key='custom',
        label='Custom',
        tone='info',
        icon='user-cog',
        detail='Administrator-managed custom role; no code-owned permission baseline applies.',
    )


def role_baseline_snapshot(roles: list[Role]) -> dict[str, object]:
    states = {role.id: role_baseline_state(role) for role in roles}
    roles_by_name = {role.name: role for role in roles}
    missing_defaults = sorted(set(DEFAULT_ROLE_DEFINITIONS) - set(roles_by_name))
    drifted = [state for state in states.values() if state.key in {'drift', 'unexpected_system'}]
    return {
        'states': states,
        'missing_defaults': missing_defaults,
        'drift_count': len(drifted) + len(missing_defaults),
        'canonical_count': sum(1 for state in states.values() if state.key == 'canonical'),
        'unexpected_system_count': sum(1 for state in states.values() if state.key == 'unexpected_system'),
    }
