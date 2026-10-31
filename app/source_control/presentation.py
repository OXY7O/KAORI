"""Committed, installation-scoped Source Control product projections (#3375).

Read-only KAORI state. No live provider calls, repository clone or cross-grant
aggregation. Every caller must enforce the local UAT scope until #724 lands.
"""

from __future__ import annotations

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.source_control import SourceInstallation, SourceRepositoryCollectionState

_MAX_UAT_INSTALLATIONS = 50


def build_source_control_overview() -> dict:
    """Read only active GitHub.com installation identities and collection states.

    Repository counts are deliberately NOT summed across installations: the
    same immutable repository may be granted to multiple installations.
    """
    records = (
        db.session.query(
            SourceInstallation,
            IntegrationInstance,
            SourceRepositoryCollectionState,
        )
        .join(
            IntegrationInstance,
            SourceInstallation.integration_instance_id == IntegrationInstance.id,
        )
        .outerjoin(
            SourceRepositoryCollectionState,
            SourceRepositoryCollectionState.installation_id == SourceInstallation.id,
        )
        .filter(
            SourceInstallation.provider_key == 'github',
            SourceInstallation.host_key == 'github.com',
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(SourceInstallation.id)
        .limit(_MAX_UAT_INSTALLATIONS + 1)
        .all()
    )
    has_more = len(records) > _MAX_UAT_INSTALLATIONS
    installations = []
    for installation, connection, collection in records[:_MAX_UAT_INSTALLATIONS]:
        committed = bool(collection is not None and collection.committed_generation > 0)
        installations.append(
            {
                'installation': installation,
                'connection': connection,
                'collection': collection,
                'committed': committed,
                'observed_count': collection.observed_count if collection is not None and committed else None,
                'coverage': collection.coverage if collection is not None and committed else 'unknown',
                'selection_scope': collection.repository_scope if collection is not None and committed else 'unknown',
                'collection_status': collection.status if collection is not None else 'not_collected',
                'last_committed_at': collection.last_committed_at if collection is not None and committed else None,
            }
        )
    committed_dates = [item['last_committed_at'] for item in installations if item['last_committed_at']]
    committed_count = sum(1 for item in installations if item['committed'])
    return {
        'installations': tuple(installations),
        'installation_count': len(installations),
        'committed_count': committed_count,
        'uncollected_count': len(installations) - committed_count,
        'has_more': has_more,
        'latest_committed_at': max(committed_dates) if committed_dates else None,
    }
