from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from sqlalchemy import (
    Integer,
    String,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
)

ROOT = Path(__file__).resolve().parents[3]
PAGINATION = ROOT / 'app/common/pagination.py'

spec = importlib.util.spec_from_file_location('kaori_pagination_contract', PAGINATION)
assert spec is not None and spec.loader is not None
pagination_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pagination_module
spec.loader.exec_module(pagination_module)
paginate_select = pagination_module.paginate_select


class Base(DeclarativeBase):
    pass


class RegistryRow(Base):
    __tablename__ = 'canonical_registry_contract_rows'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


def test_paginate_select_pages_database_backed_registry_without_materializing_all_rows() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(RegistryRow(name=f'row-{index:02d}') for index in range(1, 13))
        session.commit()

        rows, pagination = paginate_select(
            session,
            select(RegistryRow).order_by(RegistryRow.id.desc()),
            page=2,
            per_page=5,
        )

    assert [row.id for row in rows] == [7, 6, 5, 4, 3]
    assert pagination['page'] == 2
    assert pagination['per_page'] == 5
    assert pagination['total_items'] == 12
    assert pagination['total_pages'] == 3
    assert pagination['start_item'] == 6
    assert pagination['end_item'] == 10
    assert pagination['has_prev'] is True
    assert pagination['has_next'] is True
