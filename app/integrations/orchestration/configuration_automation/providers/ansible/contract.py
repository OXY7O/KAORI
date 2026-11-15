"""Bounded Ansible source/Execution Environment registration values."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)

_NONPRODUCTION = frozenset(
    {
        'development',
        'staging',
        'quality_assurance',
        'user_acceptance_testing',
        'testing',
        'non_production',
        'laboratory',
        'proof_of_concept',
        'demonstration',
        'sandbox',
    }
)


@dataclass(frozen=True, slots=True)
class AnsibleConnectionInput:
    name: str
    description: str | None
    environment: str
    profile_key: str
    repository: str
    revision: str
    ansible_core_version: str
    ansible_runner_version: str
    kubespray_release: str
    execution_environment_digest: str | None

    def fingerprint_fields(self) -> dict[str, str | None]:
        return asdict(self)


def require_registration_policy(values: AnsibleConnectionInput) -> None:
    """No generic playbook, non-approved Git URL, or production registration."""
    if not 2 <= len(values.name) <= 160 or values.environment not in _NONPRODUCTION:
        raise ValueError('Kubespray pilot registration requires an approved non-production name and environment.')
    if (
        values.profile_key != PROFILE_KEY
        or values.repository != REPOSITORY
        or values.revision != SOURCE_CANDIDATE_SHA
        or values.ansible_core_version != ANSIBLE_CORE_VERSION
        or values.ansible_runner_version != ANSIBLE_RUNNER_VERSION
        or values.kubespray_release != KUBESPRAY_RELEASE
    ):
        raise ValueError('Automation profile, Git source or version does not match the reviewed candidate.')
    digest = values.execution_environment_digest
    if digest is not None:
        import re

        if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
            raise ValueError('Execution Environment digest must be an immutable sha256 reference.')
