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
