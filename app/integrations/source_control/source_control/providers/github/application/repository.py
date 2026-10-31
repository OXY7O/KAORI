"""Database-owned GitHub installation reads and KAORI-only retirement transactions.

Provider API operations remain under the GitHub provider; this repository
works only with committed KAORI records and never deletes provider data.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from app.common.pagination import paginate_query
from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.source_control import (
    SourceInstallation,
    SourceRepository,
    SourceRepositoryCollectionState,
    SourceRepositoryGrant,
)


def get_github_installation(installation_id: int) -> SourceInstallation | None:
    """Fetch an installation; the authorized HTTP caller validates its scope."""
    return db.session.get(SourceInstallation, installation_id)


def list_github_uat_installations() -> list[SourceInstallation]:
    """Return only admitted active GitHub installation records."""
    return (
        SourceInstallation.query.join(
            IntegrationInstance, SourceInstallation.integration_instance_id == IntegrationInstance.id
        )
        .filter(
            SourceInstallation.provider_key == 'github',
            SourceInstallation.host_key == 'github.com',
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(SourceInstallation.id)
        .limit(50)
        .all()
    )


def retire_github_connection(canonical: IntegrationInstance) -> None:
    """Atomically retire a KAORI integration and disable its bindings.

    The web layer must authorize, CSRF-validate and execute the existing
    active-job deletion guard before invoking this operation.
    """
    try:
        IntegrationBinding.query.filter_by(integration_instance_id=canonical.id).update(
            {'enabled': False}, synchronize_session=False
        )
        canonical.enabled = False
        canonical.lifecycle_status = 'retired'
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def github_active_connection_base():
    """Provide the admitted GitHub connection query inside the repository."""
    return IntegrationInstance.query.filter_by(
        integration_type='source_control',
        provider_key='github',
        lifecycle_status='active',
    )


def github_connection_counts() -> tuple[int, int]:
    base = github_active_connection_base()
    total = base.count()
    ready = base.filter_by(enabled=True, lifecycle_status='active', readiness_status='ready').count()
    return total, ready


def github_committed_coverage_projection(
    selected_coverage_query: str,
    selected_coverage_environment: str,
    selected_coverage_status: str,
    requested_coverage_page: int,
    requested_coverage_per_page: int,
) -> dict[str, Any]:
    # Only committed generations with effective-dated grants are coverage
    # evidence. A tested/registered installation alone is not inventory.
    coverage_base = (
        db.session.query(
            SourceRepositoryGrant,
            SourceRepository,
            SourceInstallation,
            IntegrationInstance,
            SourceRepositoryCollectionState,
        )
        .join(SourceRepository, SourceRepository.id == SourceRepositoryGrant.repository_id)
        .join(SourceInstallation, SourceInstallation.id == SourceRepositoryGrant.installation_id)
        .join(IntegrationInstance, IntegrationInstance.id == SourceInstallation.integration_instance_id)
        .join(
            SourceRepositoryCollectionState,
            SourceRepositoryCollectionState.installation_id == SourceInstallation.id,
        )
        .filter(
            SourceRepositoryGrant.valid_until.is_(None),
            SourceRepositoryCollectionState.committed_generation > 0,
            SourceInstallation.provider_key == 'github',
            SourceInstallation.host_key == 'github.com',
            SourceRepository.provider_key == 'github',
            SourceRepository.host_key == 'github.com',
            IntegrationInstance.integration_type == 'source_control',
            IntegrationInstance.provider_key == 'github',
            IntegrationInstance.lifecycle_status == 'active',
        )
    )
    grants = coverage_base.count()
    committed_collections = (
        SourceRepositoryCollectionState.query.join(
            SourceInstallation,
            SourceInstallation.id == SourceRepositoryCollectionState.installation_id,
        )
        .join(
            IntegrationInstance,
            IntegrationInstance.id == SourceInstallation.integration_instance_id,
        )
        .filter(
            SourceRepositoryCollectionState.committed_generation > 0,
            SourceInstallation.provider_key == 'github',
            SourceInstallation.host_key == 'github.com',
            IntegrationInstance.integration_type == 'source_control',
            IntegrationInstance.provider_key == 'github',
            IntegrationInstance.lifecycle_status == 'active',
        )
        .count()
    )

    coverage_query = coverage_base
    if selected_coverage_query:
        coverage_term = f'%{selected_coverage_query}%'
        coverage_query = coverage_query.filter(
            or_(
                SourceRepository.full_name.ilike(coverage_term),
                SourceRepository.name.ilike(coverage_term),
                IntegrationInstance.name.ilike(coverage_term),
                SourceInstallation.native_installation_id.ilike(coverage_term),
            )
        )
    if selected_coverage_environment:
        coverage_query = coverage_query.filter(IntegrationInstance.environment == selected_coverage_environment)
    if selected_coverage_status:
        coverage_query = coverage_query.filter(SourceRepositoryCollectionState.coverage == selected_coverage_status)
    coverage_rows, coverage_pagination = paginate_query(
        coverage_query.order_by(
            SourceRepository.full_name.asc(),
            SourceInstallation.id.asc(),
            SourceRepositoryGrant.id.asc(),
        ),
        page=requested_coverage_page,
        per_page=requested_coverage_per_page,
    )
    coverage_environment_options = [
        item[0] for item in coverage_base.with_entities(IntegrationInstance.environment).distinct().all() if item[0]
    ]
    coverage_status_options = [
        item[0]
        for item in coverage_base.with_entities(SourceRepositoryCollectionState.coverage).distinct().all()
        if item[0]
    ]
    return {
        'grants': grants,
        'committed_collections': committed_collections,
        'coverage_rows': coverage_rows,
        'coverage_pagination': coverage_pagination,
        'coverage_environment_options': coverage_environment_options,
        'coverage_status_options': coverage_status_options,
    }


def github_committed_connection_projection(
    selected_query: str,
    selected_environment: str,
    selected_readiness: str,
    requested_page: int,
    requested_per_page: int,
) -> dict[str, Any]:
    base = github_active_connection_base()
    query = base
    if selected_query:
        term = f'%{selected_query}%'
        query = query.filter(
            or_(
                IntegrationInstance.name.ilike(term),
                IntegrationInstance.description.ilike(term),
            )
        )
    if selected_environment:
        query = query.filter(IntegrationInstance.environment == selected_environment)
    if selected_readiness:
        query = query.filter(IntegrationInstance.readiness_status == selected_readiness)

    rows, pagination = paginate_query(
        query.order_by(IntegrationInstance.created_at.desc(), IntegrationInstance.id.desc()),
        page=requested_page,
        per_page=requested_per_page,
    )
    installations = (
        SourceInstallation.query.filter(
            SourceInstallation.integration_instance_id.in_([row.id for row in rows]),
            SourceInstallation.provider_key == 'github',
            SourceInstallation.host_key == 'github.com',
        ).all()
        if rows
        else []
    )
    installation_by_instance = {row.integration_instance_id: row for row in installations}
    environment_options = [
        item[0] for item in base.with_entities(IntegrationInstance.environment).distinct().all() if item[0]
    ]
    readiness_options = [
        item[0] for item in base.with_entities(IntegrationInstance.readiness_status).distinct().all() if item[0]
    ]
    return {
        'rows': rows,
        'pagination': pagination,
        'installation_by_instance': installation_by_instance,
        'environment_options': environment_options,
        'readiness_options': readiness_options,
    }
