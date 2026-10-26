"""Committed GitHub App permission capability presentation for KAORI UAT.

Source Control provider remains authoritative. A stored Full Validation
permission result is *not* evidence that any repository was synchronized.
No GitHub API calls are made while building the workspace.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.integrations.source_control.source_control.providers.github.readiness import _CAPABILITY_PERMISSIONS

_REQUIRED = frozenset({'repository_inventory', 'source_revision'})


@dataclass(frozen=True, slots=True)
class CapabilityCopy:
    key: str
    label: str
    category: str
    description: str
    impact: str
    next_action: str


_CAPABILITIES = (
    CapabilityCopy(
        'repository_inventory',
        'Repository Inventory',
        'Inventory',
        'Checks App metadata permission needed to discover granted repositories.',
        'Permits a separate authorized repository inventory synchronization.',
        'Run Full Validation; then synchronize repositories separately.',
    ),
    CapabilityCopy(
        'source_revision',
        'Source Revision',
        'Source Control',
        'Checks read access for exact default-branch SHA evidence.',
        'Supports committed source revision correlation after synchronization.',
        'Grant Contents: read and rerun Full Validation if unavailable.',
    ),
    CapabilityCopy(
        'pull_requests',
        'Pull Requests',
        'Collaboration',
        'Checks optional Pull Requests: read permission.',
        'Supports authorized pull-request correlations, not historical coverage by itself.',
        'Grant Pull Requests: read only when an approved workflow requires it.',
    ),
    CapabilityCopy(
        'workflow_runs',
        'Workflow Runs',
        'Automation',
        'Checks optional Actions: read permission.',
        'Allows workflow run evidence when an authorized collection exists.',
        'Grant Actions: read only for approved workflow correlation.',
    ),
    CapabilityCopy(
        'check_runs',
        'Check Runs',
        'Assurance',
        'Checks optional Checks: read permission.',
        'Allows check-run correlation with committed source evidence.',
        'Grant Checks: read only for approved check-run collection.',
    ),
    CapabilityCopy(
        'deployments',
        'Deployments',
        'Delivery',
        'Checks optional Deployments: read permission.',
        'Allows deployment correlation when explicitly authorized.',
        'Grant Deployments: read only for approved deployment correlation.',
    ),
)


def _capability_status(
    *, observed: bool, state: object, required: bool
) -> tuple[bool, bool, str, str, str]:
    """Project a committed permission state without changing admission semantics."""
    verified = bool(observed and state == 'permission_verified')
    unavailable = bool(observed and state == 'permission_unavailable')
    if verified:
        label = 'Permission Verified'
        status_tone = 'normal'
        status_icon = 'circle-check'
    elif unavailable:
        label = 'Permission Unavailable'
        status_tone = 'critical' if required else 'warning'
        status_icon = 'triangle-alert'
    else:
        label = 'Not Validated'
        status_tone = 'warning'
        status_icon = 'circle-help'
    return verified, unavailable, label, status_tone, status_icon


def github_capability_context(canonical: Any) -> dict[str, Any]:
    """Project only committed Full Validation permission states, never live grants."""
    raw = canonical.metadata_json
    metadata = raw.get('github_validation') if isinstance(raw, Mapping) else None
    evidence = metadata if isinstance(metadata, Mapping) else {}
    states_value = evidence.get('capability_states')
    states = states_value if isinstance(states_value, Mapping) else {}
    observed = (
        evidence.get('profile') == 'github-app-readiness-v1'
        and bool(evidence.get('last_validated_at'))
        and bool(states)
    )

    rows: list[dict[str, Any]] = []
    for capability in _CAPABILITIES:
        permissions = _CAPABILITY_PERMISSIONS[capability.key]
        required = capability.key in _REQUIRED
        verified, unavailable, label, status_tone, status_icon = _capability_status(
            observed=observed, state=states.get(capability.key), required=required
        )
        required_label = ', '.join(f'{scope}: read' for scope in sorted(permissions))
        evidence_text = (
            'The latest committed Full Validation recorded the required read permissions.'
            if verified
            else 'The latest committed Full Validation did not confirm the required permissions.'
            if unavailable
            else 'No committed Full Validation permission assessment is available for this capability.'
        )
        status_key = (
            'ready' if verified else 'unverified' if not observed else 'blocked' if required else 'optional_gap'
        )
        rows.append(
            {
                'key': capability.key,
                'label': capability.label,
                'category': capability.category,
                'description': capability.description,
                'required': required,
                'available': verified,
                'status_label': label,
                'status_key': status_key,
                'status_tone': status_tone,
                'status_icon': status_icon,
                'probe': 'GitHub App installation permission assessment from committed Full Validation.',
                'technical_checks': [
                    {
                        'label': 'App Read Permission Contract',
                        'status': 'available' if verified else 'not_observed',
                        'status_label': label,
                        'evidence': evidence_text,
                        'query': required_label,
                        'registered_query': required_label,
                        'series_count_display': '',
                        'value_summary': '',
                        'error_detail': '',
                        'tone': 'normal' if verified else 'warning',
                        'icon': 'circle-check' if verified else 'circle-help',
                    }
                ],
                'success_criteria': f'Full Validation confirms {required_label} for this installation.',
                'configuration_guidance': 'Manage the GitHub App installation grants in GitHub.',
                'impact': capability.impact,
                'remediation': []
                if verified
                else [
                    'Review the installation permissions in GitHub.',
                    'Rerun Full Validation and separately authorize collection where relevant.',
                ],
                'evidence': evidence_text,
                'next_action': 'No permission change required; repository evidence needs its own synchronization.'
                if verified
                else capability.next_action,
            }
        )

    verified_count = sum(bool(row['available']) for row in rows)
    required_missing = sum(row['required'] and not row['available'] for row in rows) if observed else None
    return {
        'capability_rows': rows,
        'capability_summary': {
            'total': len(rows),
            'verified': verified_count,
            'required_missing': required_missing,
            'optional_verified': sum(row['available'] and not row['required'] for row in rows),
            'observed': bool(observed),
            'profile': str(evidence.get('profile') or 'github-app-readiness-v1'),
            'validated_at': str(evidence.get('last_validated_at') or ''),
        },
    }
