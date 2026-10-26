"""GitHub App capability-specific Full Validation/readiness semantics (#2741).

No single Test Connection response, repository listing, or GitHub Actions
run can imply that every Source Control capability is operational.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.source_control.source_control.providers.github.transport import InstallationReadiness

_CAPABILITY_PERMISSIONS = {
    'repository_inventory': frozenset({'metadata'}),
    'source_revision': frozenset({'metadata', 'contents'}),
    'pull_requests': frozenset({'metadata', 'pull_requests'}),
    'workflow_runs': frozenset({'metadata', 'actions'}),
    'check_runs': frozenset({'metadata', 'checks'}),
    'deployments': frozenset({'metadata', 'deployments'}),
}


@dataclass(frozen=True, slots=True)
class GitHubReadinessAssessment:
    status: str
    capability_states: dict[str, str]
    repository_scope: str
    coverage_hint: str
    reason: str


def assess_installation_readiness(evidence: InstallationReadiness) -> GitHubReadinessAssessment:
    """Assess permission coverage conservatively; never fabricate validation."""
    if evidence.repository_selection not in {'all', 'selected'}:
        return GitHubReadinessAssessment(
            status='blocked',
            capability_states={},
            repository_scope='unknown',
            coverage_hint='unverified',
            reason='Repository grant scope is unknown.',
        )
    permissions = frozenset(evidence.permission_names)
    states = {
        capability: 'permission_verified' if required <= permissions else 'permission_unavailable'
        for capability, required in _CAPABILITY_PERMISSIONS.items()
    }
    if states['repository_inventory'] != 'permission_verified':
        status = 'blocked'
        reason = 'GitHub metadata access is missing.'
    elif states['source_revision'] != 'permission_verified':
        status = 'validation_required'
        reason = 'Metadata access is confirmed; Contents:read is required for repository SHA evidence.'
    else:
        # Ready means installation *connection* readiness for a subsequent
        # authoritative repository sync. It never asserts that collection
        # coverage, history or downstream GitHub capabilities are ready.
        status = 'ready'
        reason = 'GitHub App installation metadata and source-revision permissions validated.'
    return GitHubReadinessAssessment(
        status=status,
        capability_states=states,
        repository_scope=evidence.repository_selection,
        coverage_hint='selected_repositories' if evidence.repository_selection == 'selected' else 'all_repositories',
        reason=reason,
    )
