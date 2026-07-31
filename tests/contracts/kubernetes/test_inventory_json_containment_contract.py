from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SERVICE_SOURCE = ROOT / 'app/inventory/resources/services.py'
STORAGE_SOURCE = ROOT / 'app/inventory/resources/storage.py'


def test_service_selector_matching_uses_postgresql_jsonb_containment() -> None:
    source = SERVICE_SOURCE.read_text()

    assert 'from sqlalchemy.dialects.postgresql import JSONB' in source
    assert 'cast(PodInventory.labels, JSONB).contains(selector)' in source
    assert 'PodInventory.labels.contains(selector)' not in source
    assert "dialect == 'postgresql'" in source
    assert '_selector_matches' in source


def test_storage_pvc_relationships_use_postgresql_jsonb_containment() -> None:
    source = STORAGE_SOURCE.read_text()

    assert 'from sqlalchemy.dialects.postgresql import JSONB' in source
    assert 'cast(PodInventory.persistent_volume_claims, JSONB).contains([name])' in source
    assert 'PodInventory.persistent_volume_claims.contains([name])' not in source
    assert "dialect == 'postgresql'" in source
    assert '.limit(8)' in source


def test_postgresql_jsonb_containment_compiles_to_at_operator() -> None:
    from sqlalchemy import JSON, Column, MetaData, Table, cast, select
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.dialects.postgresql import JSONB

    table = Table(
        'pod_inventory',
        MetaData(),
        Column('labels', JSON),
        Column('persistent_volume_claims', JSON),
    )
    statements = (
        select(table).where(cast(table.c.labels, JSONB).contains({'app': 'demo'})),
        select(table).where(cast(table.c.persistent_volume_claims, JSONB).contains(['claim'])),
    )

    for statement in statements:
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        assert '@>' in compiled
        assert ' LIKE ' not in compiled
