from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.migration

ROOT = Path(__file__).resolve().parents[2]


def _load_verifier():
    path = ROOT / 'scripts/verify_migration_graph.py'
    spec = importlib.util.spec_from_file_location('kaori_migration_graph_verifier', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_migration_graph_has_one_root_and_one_head() -> None:
    verifier = _load_verifier()
    revisions = verifier.load_migrations(ROOT / 'migrations/versions')
    errors, roots, heads = verifier.validate_graph(revisions)

    assert errors == []
    assert len(roots) == 1
    assert len(heads) == 1
    assert len(revisions) >= 1


def test_migration_revision_ids_are_unique() -> None:
    verifier = _load_verifier()
    revisions = verifier.load_migrations(ROOT / 'migrations/versions')
    revision_ids = [item.revision for item in revisions]

    assert len(revision_ids) == len(set(revision_ids))


def test_migration_revision_ids_fit_alembic_version_column() -> None:
    verifier = _load_verifier()
    revisions = verifier.load_migrations(ROOT / 'migrations/versions')
    too_long = {item.path.name: item.revision for item in revisions if len(item.revision) > 32}

    assert too_long == {}, (
        'Alembic stores the active revision in alembic_version.version_num varchar(32); '
        f'oversized revision IDs: {too_long}'
    )

def test_resolver_global_control_uses_expression_unique_index() -> None:
    migration = (ROOT / 'migrations/versions/20260723_resolver_controls.py').read_text()
    model = (ROOT / 'app/models/resolver.py').read_text()

    expected_name = 'uq_resolver_operational_control_scope'
    expected_expression = "COALESCE(cluster_id, '__global__')"

    assert expected_name in migration
    assert expected_expression in migration
    assert expected_name in model
    assert 'func.coalesce(ResolverOperationalControl.cluster_id' in model

