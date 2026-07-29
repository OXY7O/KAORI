from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / "app/templates/inventory/services/partials/_summary_cards.html"
TABLE = ROOT / "app/templates/inventory/services/partials/_table_content.html"
DETAIL = ROOT / "app/templates/inventory/services/partials/_service_detail_content.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_service_inventory_copy_uses_requested_display_capitalization() -> None:
    summary = read(SUMMARY)
    table = read(TABLE)

    expected = [
        "Services in the Current Result",
        "Internal Only Service Exposure",
        "Services Exposed through Node Ports",
        "Services Exposed through External Load Balancers",
        "Node Level Exposure Endpoints",
        "NodePort and LoadBalancer Combined",
    ]
    for copy in expected:
        assert copy in summary

    removed = [
        "Services in the current result.",
        "Internal-only service exposure.",
        "Services exposed through node ports.",
        "Services exposed through external load balancers.",
        "Node-level exposure endpoints.",
        "NodePort and LoadBalancer combined.",
    ]
    for copy in removed:
        assert copy not in summary

    assert "{{ 'Service' if pagination.total_items == 1 else 'Services' }}" in table
    assert "{{ 'service' if pagination.total_items == 1 else 'services' }}" not in table


def test_service_detail_cards_share_tallest_height_and_detail_label_scale() -> None:
    detail = read(DETAIL)

    assert "grid items-stretch gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" in detail
    assert "min-h-96" not in detail
    assert "min-h-[28rem]" not in detail
    assert "min-h-[30rem]" not in detail

    assert detail.count("badge_size='detail'") >= 4
    assert "detail.status_row('Type', service.type, service_type_tone, none, 'detail')" in detail
    assert "detail.status_row('IP Family Policy', service.ip_family_policy, ip_policy_tone, none, 'detail')" in detail
    assert "detail.status_row('Internal Traffic', service.internal_traffic_policy, internal_traffic_tone, none, 'detail')" in detail
    assert "detail.status_row('External Traffic', service.external_traffic_policy, external_traffic_tone, none, 'detail')" in detail
    assert "detail.status_row('Publish Not-Ready', 'Enabled' if service.publish_not_ready_addresses else 'Disabled'" in detail


def test_service_detail_semantic_tones_cover_requested_values_and_tip_is_removed() -> None:
    detail = read(DETAIL)

    assert "normalized_service_type in ['clusterip', 'headless']" in detail
    assert "normalized_ip_policy == 'singlestack'" in detail
    assert "normalized_internal_traffic == 'cluster'" in detail
    assert "normalized_external_traffic == 'cluster'" in detail
    assert "'warning' if service.publish_not_ready_addresses else 'unknown'" in detail

    assert "Endpoint Snapshot" not in detail
    assert "Selector and endpoint readiness from the latest inventory snapshot." not in detail
