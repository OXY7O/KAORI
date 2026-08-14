from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[3] / 'app/inventory/kubernetes/topology/contracts.py'
SPEC = importlib.util.spec_from_file_location('kaori_inventory_topology_contracts', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
TopologySelection = MODULE.TopologySelection


def test_depth_one_keeps_topology_at_cluster_namespace_and_level_one_resources() -> None:
    selection = TopologySelection.from_filters(scope='all', depth='1')

    assert selection.include_level_1 is True
    assert selection.include_level_2 is False
    assert selection.include_pods is False
    assert selection.include_all_relationships is False


def test_full_depth_enables_pods_and_all_relationships() -> None:
    selection = TopologySelection.from_filters(scope='all', depth='full')

    assert selection.include_level_1 is True
    assert selection.include_level_2 is True
    assert selection.include_pods is True
    assert selection.include_all_relationships is True


def test_scope_selection_exposes_only_the_requested_resource_family() -> None:
    selection = TopologySelection.from_filters(scope='networking', depth='2')

    assert selection.show_networking is True
    assert selection.show_compute is False
    assert selection.show_configuration is False
    assert selection.show_storage is False
