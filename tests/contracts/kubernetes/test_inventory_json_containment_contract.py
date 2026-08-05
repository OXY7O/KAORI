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


def test_storage_pvc_relationships_use_postgresql_jsonb_overlap() -> None:
    source = STORAGE_SOURCE.read_text()

    assert 'from sqlalchemy.dialects.postgresql import JSONB, array' in source
    assert "cast(PodInventory.persistent_volume_claims, JSONB).op('?|')" in source
    assert 'array(sorted(names))' in source
    assert 'PodInventory.persistent_volume_claims.contains([name])' not in source
    assert 'claims[:200]' not in source
    assert "dialect == 'postgresql'" in source
    assert '.limit(8)' in source


def test_postgresql_jsonb_containment_and_overlap_compile_to_native_operators() -> None:
    from sqlalchemy import JSON, Column, MetaData, Table, cast, select
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.dialects.postgresql import JSONB, array

    table = Table(
        'pod_inventory',
        MetaData(),
        Column('labels', JSON),
        Column('persistent_volume_claims', JSON),
    )
    statements = (
        (select(table).where(cast(table.c.labels, JSONB).contains({'app': 'demo'})), '@>'),
        (
            select(table).where(
                cast(table.c.persistent_volume_claims, JSONB).op('?|')(array(['claim']))
            ),
            '?|',
        ),
    )

    for statement, operator in statements:
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        assert operator in compiled
        assert ' LIKE ' not in compiled
