"""Evidence-safe GitHub webhook → SC-03 reconciliation intent boundary.

No provider call, task enqueue or state publication occurs in this module.
Delivery IDs are only transport evidence; repository-scoped refresh requires
an independently *committed* repository identity and current installation
grant. Missing scope causes installation-wide grant reconciliation instead
of trusting an attacker-supplied repository ID.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError
from app.integrations.source_control.source_control.providers.github.webhook_inbox import (
    _eligible_installation,
)
from app.models.source_control import (
    SourceInstallation,
    SourceRepository,
    SourceRepositoryGrant,
    SourceWebhookDelivery,
)

_INSTALLATION_EVENTS = frozenset({'installation', 'installation_repositories'})
_REPOSITORY_EVENTS = frozenset({'repository', 'workflow_run'})


@dataclass(frozen=True, slots=True)
class ReconciliationIntent:
    """Provider-neutral target, not a new JobExecution or source observation."""

    integration_instance_id: int
    installation_record_id: int
    scope: str
    repository_record_id: int | None
    delivery_record_id: int
    reason: str


def resolve_reconciliation_intent(
    *,
    session: Session,
    installation: SourceInstallation,
    delivery_record_id: int,
) -> ReconciliationIntent:
    """Resolve admitted transport evidence to a safe bounded refresh target.

    Must be called on a *committed* delivery from an independently scheduled
    inbox-consumer transaction. The caller is responsible for post-commit
    dispatch through the existing JobExecution subsystem only after SC-03
    defines its authoritative reconciliation task. This function never
    accepts repository names or native IDs supplied by a caller.
    """
    _eligible_installation(installation)
    if installation.id is None or delivery_record_id <= 0:
        raise GitHubWebhookError('Source Control delivery identity is not committed.')
    delivery = session.get(SourceWebhookDelivery, delivery_record_id)
    if delivery is None or delivery.installation_id != installation.id:
        raise GitHubWebhookError('Source Control delivery does not belong to this installation.')
    if delivery.processing_state not in {'received', 'retry_pending'}:
        raise GitHubWebhookError('Source Control delivery is not awaiting reconciliation.')
    if delivery.event_type not in _INSTALLATION_EVENTS | _REPOSITORY_EVENTS:
        raise GitHubWebhookError('Source Control delivery does not map to supported reconciliation.')

    canonical_id = installation.integration_instance_id
    if canonical_id is None:
        raise GitHubWebhookError('Canonical Source Control installation is unavailable.')

    if delivery.event_type in _REPOSITORY_EVENTS and delivery.repository_native_id_hint is not None:
        # Repository identity is provider-native and installation-independent;
        # current authorized grant is independently recorded by SC-03. No
        # name matching, mutable ref, payload-derived permission or other App.
        repository = session.execute(
            select(SourceRepository)
            .join(
                SourceRepositoryGrant,
                SourceRepositoryGrant.repository_id == SourceRepository.id,
            )
            .where(
                SourceRepository.provider_key == installation.provider_key,
                SourceRepository.host_key == installation.host_key,
                SourceRepository.native_repository_id == delivery.repository_native_id_hint,
                SourceRepositoryGrant.installation_id == installation.id,
                SourceRepositoryGrant.valid_until.is_(None),
                SourceRepositoryGrant.access_status == 'granted',
            )
        ).scalar_one_or_none()
        if repository is not None:
            return ReconciliationIntent(
                integration_instance_id=canonical_id,
                installation_record_id=installation.id,
                scope='repository',
                repository_record_id=repository.id,
                delivery_record_id=delivery.id,
                reason='Current committed installation grant permits targeted refresh.',
            )

    # Repository hint is unknown, grant has changed or event changes the
    # installation itself: re-check grants from GitHub using installation
    # authority; never target an unproven repository or mark it deleted.
    return ReconciliationIntent(
        integration_instance_id=canonical_id,
        installation_record_id=installation.id,
        scope='installation',
        repository_record_id=None,
        delivery_record_id=delivery.id,
        reason='Installation grant reconciliation required before targeting repositories.',
    )
