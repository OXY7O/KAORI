"""Immutable Kubespray source candidate policy and committed evidence qualification.

GitHub owns transport and Git objects; Infrastructure Automation owns the
review-only eligibility decision. Source qualification never admits a worker,
credentials, target, Plan approval or infrastructure mutation.
"""

from __future__ import annotations

from app.infrastructure_automation.kubernetes.kubespray_preflight import KUBESPRAY_RELEASE

REPOSITORY = 'OXY7O/kaori-operations'
# Independently reviewed non-executable profile, merged upstream in PR #6.
SOURCE_CANDIDATE_SHA = '63db48309cbb6d261c27cf54f60bfe885a21f770'
PROFILE_KEY = 'kubernetes_lifecycle'
ANSIBLE_CORE_VERSION = '2.19.15'
ANSIBLE_RUNNER_VERSION = '2.4.3'


def committed_source_state(metadata: object) -> str:
    """Return checked, blocked or not_checked from exact committed source evidence."""
    metadata = metadata if isinstance(metadata, dict) else {}
    evidence = metadata.get('source_validation')
    evidence = evidence if isinstance(evidence, dict) else {}
    observed = str(evidence.get('status') or '').strip()
    matches_source = (
        evidence.get('repository') == metadata.get('source_repository') == REPOSITORY
        and evidence.get('revision') == metadata.get('source_sha') == SOURCE_CANDIDATE_SHA
        and evidence.get('profile_key') == metadata.get('profile_key') == PROFILE_KEY
        and evidence.get('checked_files') == 5
        and evidence.get('operation_authorized') is False
        and metadata.get('ansible_core_version') == ANSIBLE_CORE_VERSION
        and metadata.get('ansible_runner_version') == ANSIBLE_RUNNER_VERSION
        and metadata.get('kubespray_release') == KUBESPRAY_RELEASE
    )
    checked = observed == 'source_checked' and matches_source
    blocked = observed in {'blocked', 'rejected', 'failed'} or (observed == 'source_checked' and not checked)
    return 'checked' if checked else ('blocked' if blocked else 'not_checked')
