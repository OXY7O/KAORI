from __future__ import annotations

from app.inventory.formatting import (
    convert_storage_to_gib,
    format_gib,
    format_kubernetes_size,
    format_quota_value,
)


def test_inventory_kubernetes_quantities_have_stable_human_readable_units() -> None:
    assert format_kubernetes_size('1024Ki') == '1 MiB'
    assert format_kubernetes_size('1Gi') == '1 GiB'
    assert format_kubernetes_size('1G') == '953.7 MiB'
    assert format_kubernetes_size('-') == '-'
    assert format_kubernetes_size('invalid') == '-'


def test_inventory_storage_conversion_and_quota_formatting_are_consistent() -> None:
    assert convert_storage_to_gib('1048576Ki') == 1.0
    assert format_gib(1.5) == '1.5 GiB'
    assert format_gib(0) == '-'
    assert format_quota_value('requests.memory', '1024Mi') == '1 GiB'
    assert format_quota_value('pods', '25') == '25'
