"""SC-03 committed inventory projection never queries GitHub or broadens installation."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.integrations.source_control.repository_inventory import read_installation_inventory
from app.models.integration import IntegrationInstance
from app.models.source_control import (
    SourceAccount, SourceInstallation, SourceRepository,
    SourceRepositoryCollectionState, SourceRepositoryGrant,
)
from datetime import UTC, datetime
import pytest


@pytest.fixture
def read_db():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(bind=engine, tables=[
        IntegrationInstance.__table__,
        SourceAccount.__table__,
        SourceInstallation.__table__,
        SourceRepository.__table__,
        SourceRepositoryGrant.__table__,
        SourceRepositoryCollectionState.__table__,
    ])
    with Session(engine) as session:
        account = SourceAccount(
            provider_key='github', host_key='github.com', native_account_id='1',
        )
        session.add(account)
        session.flush()
        installations = []
        for number in (5, 6):
            provider = IntegrationInstance(
                name=f'Github {number}', integration_type='source_control',
                provider_key='github', adapter_key='github_rest_v3',
                lifecycle_status='active', readiness_status='validation_required',
            )
            session.add(provider)
            session.flush()
            installation = SourceInstallation(
                integration_instance_id=provider.id, account_id=account.id,
                host_key='github.com', provider_key='github', native_app_id='2',
                native_installation_id=str(number), repository_scope='selected',
            )
            session.add(installation)
            session.flush()
            installations.append(installation.id)
        repo = SourceRepository(
            provider_key='github', host_key='github.com',
            native_repository_id='15', full_name='org/private-repo',
            default_branch='main', visibility='private',
            provider_presence='observed',
        )
        session.add(repo)
        session.flush()
        now = datetime.now(UTC)
        session.add(SourceRepositoryGrant(
            installation_id=installations[0], repository_id=repo.id,
            access_status='granted', valid_from=now, last_observed_at=now,
        ))
        session.add(SourceRepositoryCollectionState(
            installation_id=installations[0], next_generation=1,
            committed_generation=1, status='committed',
            repository_scope='selected', coverage='exhaustive_installation_grants',
            observed_count=1, last_committed_at=now,
        ))
        session.commit()
        yield session, installations
    engine.dispose()


def test_projection_uses_only_authorized_installation(read_db):
    session, installations = read_db
    one = read_installation_inventory(session, authorized_installation_id=installations[0])
    assert one.total == 1
    assert len(one.rows) == 1
    assert one.rows[0].full_name == 'org/private-repo'
    other = read_installation_inventory(session, authorized_installation_id=installations[1])
    assert other.total is None
    assert other.rows == ()
    assert other.observed_count is None


def test_missing_coverage_never_infers_empty_source_scope(read_db):
    session, installations = read_db
    other = read_installation_inventory(session, authorized_installation_id=installations[1])
    assert other.collection_status == 'not_collected'
    assert other.coverage == 'unknown'
    assert other.total is None


@pytest.mark.parametrize('size', [0, 1, 3, 100, True])
def test_pagination_only_uses_kaori_page_sizes(read_db, size):
    session, installations = read_db
    with pytest.raises(ValueError):
        read_installation_inventory(
            session, authorized_installation_id=installations[0],
            per_page=size,
        )


@pytest.mark.parametrize('identity', [0, -1, True, None])
def test_unqualified_installation_is_rejected(read_db, identity):
    session, _ = read_db
    with pytest.raises(ValueError):
        read_installation_inventory(session, authorized_installation_id=identity)


def test_no_live_provider_request_in_read_projection():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] /
              'app/integrations/source_control/repository_inventory.py').read_text()
    assert 'requests' not in source
    assert 'GitHubAppClient' not in source
    assert 'access_tokens' not in source
    assert 'integration_instance_id' not in source.split('def read_installation_inventory(')[1]
