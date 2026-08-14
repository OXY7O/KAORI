from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / 'app/inventory/kubernetes/formatting.py'
SPEC = spec_from_file_location('kaori_inventory_formatting', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
FORMATTING = module_from_spec(SPEC)
SPEC.loader.exec_module(FORMATTING)


def test_node_capacity_aggregation_preserves_precision_until_final_rounding() -> None:
    values = ['1064960Ki'] * 10  # 1.015625 GiB each.

    memory_total = round(sum(FORMATTING.convert_ki_to_gib(value) for value in values), 1)
    storage_total = round(sum(FORMATTING.convert_storage_to_gib(value) for value in values), 1)

    assert memory_total == 10.2
    assert storage_total == 10.2
