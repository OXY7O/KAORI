"""#4769: readable committed ResourceQuota evidence and canonical record Guide."""

from pathlib import Path

import pytest
from jinja2 import Environment

from app.kubernetes.analytics.workload.formatting import (
    build_resource_quota_items,
    format_resource_quota_value,
)

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html"
QUOTA_DOMAIN = ROOT / "app/kubernetes/analytics/workload/quota.py"


@pytest.mark.parametrize(
    ("key", "raw", "display"),
    [
        ("requests.storage", 107374182400.0, "100.00 GiB"),
        ("requests.storage", 0.0, "0.00 GiB"),
        ("requests.ephemeral-storage", 1073741824.0, "1.00 GiB"),
        ("limits.ephemeral-storage", 2147483648.0, "2.00 GiB"),
        ("limits.memory", 8589934592.0, "8.00 GiB"),
        ("requests.cpu", 2.0, "2.00 core"),
        ("pods", 20.0, "20 pods"),
        ("configmaps", 50.0, "50"),
        ("secrets", 50.0, "50"),
        ("count/deployments.apps", 4.0, "4"),
    ],
)
def test_resource_quota_display_uses_correct_unit(
    key: str, raw: float, display: str
) -> None:
    assert format_resource_quota_value(key, raw) == display


def test_hard_and_used_values_remain_independent_and_immutable() -> None:
    hard = {"requests.storage": 107374182400.0, "pods": 20.0, "secrets": 50.0}
    used = {"requests.storage": 1073741824.0, "pods": 0.0}
    hard_before = hard.copy()
    used_before = used.copy()

    hard_items = build_resource_quota_items(hard)
    used_items = build_resource_quota_items(used)

    assert {"label": "requests.storage", "value": "100.00 GiB"} in hard_items
    assert {"label": "requests.storage", "value": "1.00 GiB"} in used_items
    assert {"label": "Pods", "value": "0 pods"} in used_items
    assert all(item["label"] != "secrets" for item in used_items)
    assert build_resource_quota_items({}) == []
    assert hard == hard_before
    assert used == used_before


def test_tenant_quota_records_guide_and_modal_panels_follow_existing_ui() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")
    Environment(autoescape=True).parse(source)

    guide_id = "kubernetes-analytics-workload-tenant-quota-records-guide"
    assert source.count(guide_id) == 1
    assert "info_tip.render(" in source
    assert "Tenant Quota Records Guide" in source
    assert "placement='right', variant='guide'" in source
    header = source.split("Tenant Quota Records</h3>", 1)[1]
    assert guide_id in header.split("Filter namespace quota evidence", 1)[0]
    assert "record_filter.form(" in source
    assert "evidence_list.shell('Tenant Quota Records', embedded=true)" in source

    assert "row.quota_objects|length > 1" in source
    assert "row.quota_objects|length == 1" in source
    assert "md:grid-cols-2" in source
    assert "lg:grid-cols-2" in source
    assert 'aria-label="{{ quota.name }} hard boundary"' in source
    assert 'aria-label="{{ quota.name }} observed used"' in source
    assert "quota.hard_items|length" in source
    assert "quota.used_items|length" in source
    assert "quota.hard_items" in source
    assert "quota.used_items" in source
    assert "divide-y divide-outline-subtle" in source
    assert source.count("tabular-nums text-content-primary") >= 2
    assert 'class="col-span-full"' in source
    assert "No ResourceQuota Object Available" in source
    assert "Used-value evidence is unavailable." in source
    assert "row.missing_key_labels" in source
    assert "Combined ResourceQuota coverage includes every required" in source
    assert "Runtime Demand Interpretation" in source
    assert "Recommended Action" in source


def test_storage_format_is_display_only_and_raw_quota_drives_pressure() -> None:
    source = QUOTA_DOMAIN.read_text(encoding="utf-8")
    assert "build_resource_quota_items(hard_values)" in source
    assert "build_resource_quota_items(data['used_objects'].get(name, {}))" in source
    assert "get_effective_quota_resource(" in source
    assert "raw_percent(used_value, hard_value)" in source
    assert "for name, hard_values in sorted(data['hard_objects'].items())" in source
