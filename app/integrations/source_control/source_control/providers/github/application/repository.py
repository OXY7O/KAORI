"""Database-owned GitHub installation reads and KAORI-only retirement transactions.

Provider API operations remain under the GitHub provider; this repository
works only with committed KAORI records and never deletes provider data.
"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.source_control import SourceInstallation


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
