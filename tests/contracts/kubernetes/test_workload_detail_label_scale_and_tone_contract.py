from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_workload_detail_cards_use_detail_scale_labels() -> None:
    template = _read("app/templates/inventory/workloads/partials/_workload_detail_content.html")

    assert "detail.detail_card('Object Identity'" in template
    assert "badge_size='detail'" in template
    assert "detail.detail_card('Runtime State', 'activity', workload.state_display, 'status', status_tone, 'min-h-80', 'detail')" in template
    assert "detail.detail_card('Delivery & Placement', 'route', workload.update_strategy, 'status', update_strategy_tone, 'min-h-[28rem]', 'detail')" in template
    assert "table_label.metadata_label(workload.type, 'boxes', false, 'detail')" in template
    assert "table_label.status_label(workload.state_display, status_tone, none, 'detail')" in template


def test_workload_context_values_use_semantic_detail_labels() -> None:
    template = _read("app/templates/inventory/workloads/partials/_workload_detail_content.html")

    expected_tone_entries = (
        "'recreate': 'warning'",
        "'always': 'normal'",
        "'clusterfirst': 'normal'",
        "'ifnotpresent': 'normal'",
    )
    for entry in expected_tone_entries:
        assert entry in template

    assert "detail.metadata_row('Kind', workload.type, 'boxes')" in template
    assert "row.label == 'Restart Policy'" in template
    assert "row.label == 'DNS Policy'" in template
    assert "row.label == 'Update Strategy'" in template
    assert "detail.status_row(row.label, row.value" in template
    assert "table_label.metadata_label(container.kind, 'container', false, 'detail')" in template
    assert "table_label.status_label(container.pull_policy, pull_policy_tones.get(normalized_pull_policy, 'unknown'), none, 'detail')" in template


def test_shared_detail_component_supports_detail_sized_badges() -> None:
    template = _read("app/templates/components/details/_detail_content.html")

    assert "badge_size='compact'" in template
    assert "status_row(label, value, tone='unknown', icon=None, size='compact')" in template
    assert "table_label.status_label(badge, badge_tone, none, badge_size)" in template
    assert "table_label.metadata_label(badge, none, false, badge_size)" in template
