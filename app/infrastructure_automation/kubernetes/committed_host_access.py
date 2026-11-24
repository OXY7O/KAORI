"""Internal, non-authorizing pilot access currentness correlation (#5163)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy.orm import joinedload, load_only

from app.extensions.db import db
from app.infrastructure_automation.host_access_reference import assess_bound_host_access_references
from app.models.automation import AutomationHostAccessBinding, AutomationInventoryAssignment
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import (
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)


def _member_reference(
    connection: IntegrationInstance, assignment: AutomationInventoryAssignment, now: datetime
) -> tuple[str, str, str, str] | None:
    binding = db.session.get(AutomationHostAccessBinding, assignment.id, populate_existing=True)
    if binding is None:
        return None
    representation = db.session.get(
        SecretProviderRepresentation,
        binding.secret_representation_id,
        populate_existing=True,
        options=[
            load_only(
                SecretProviderRepresentation.id,
                SecretProviderRepresentation.secret_identity_id,
                SecretProviderRepresentation.integration_instance_id,
                SecretProviderRepresentation.provider_key,
                SecretProviderRepresentation.provider_namespace,
                SecretProviderRepresentation.mount,
                SecretProviderRepresentation.path_sha256,
                SecretProviderRepresentation.representation_role,
                SecretProviderRepresentation.observation_status,
                SecretProviderRepresentation.current_version,
                SecretProviderRepresentation.last_observed_at,
            ),
            joinedload(SecretProviderRepresentation.secret_identity),
        ],
    )
    if representation is None:
        return None
    provider = db.session.get(IntegrationInstance, representation.integration_instance_id, populate_existing=True)
    collection = (
        SecretInventoryCollectionState.query.filter_by(
            integration_instance_id=representation.integration_instance_id,
            provider_namespace=representation.provider_namespace,
            mount=representation.mount,
        )
        .populate_existing()
        .one_or_none()
    )
    version = (
        SecretVersionObservation.query.filter_by(representation_id=representation.id, version=binding.secret_version)
        .populate_existing()
        .one_or_none()
    )
    if provider is None or collection is None or version is None:
        return None
    review = assess_bound_host_access_references(
        binding=binding,
        connection=connection,
        assignment=assignment,
        provider=provider,
        representation=representation,
        collection=collection,
        version=version,
        now=now,
    )
    generation = collection.last_committed_at
    if review.state != 'references_recorded' or review.fingerprint is None or generation is None:
        return None
    # Match the committed metadata UTC convention for SQLite round trips.
    generation = generation.replace(tzinfo=UTC) if generation.tzinfo is None else generation.astimezone(UTC)
    return (
        assignment.host_id,
        binding.host_revision,
        review.fingerprint,
        generation.isoformat(),
    )


def committed_pilot_access_fingerprint(
    connection: IntegrationInstance, assignments: list[AutomationInventoryAssignment], *, now: datetime
) -> str | None:
    """Hash exact committed metadata only, never grant credential use or SSH trust.

    Caller owns exact canonical connection scope. No Secret metadata is returned.
    """
    if len(assignments) != 3 or now.tzinfo is None:
        return None
    members: list[tuple[str, str, str, str]] = []
    for assignment in assignments:
        if assignment.integration_instance_id != connection.id or assignment.enabled is not True:
            return None
        reference = _member_reference(connection, assignment, now)
        if reference is None:
            return None
        members.append(reference)
    if len({member[0] for member in members}) != 3:
        return None
    material = {'schema_version': 1, 'connection_id': connection.id, 'members': sorted(members)}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
