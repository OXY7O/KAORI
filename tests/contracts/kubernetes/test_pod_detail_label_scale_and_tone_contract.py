from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_pod_detail_cards_use_detail_scale_labels() -> None:
    template = read("app/templates/inventory/pods/partials/_pod_detail_content.html")

    expected_cards = (
        "detail.detail_card('Pod Identity', 'badge-info', pod.age, class_name='min-h-96', badge_size='detail')",
        "detail.detail_card('Placement & Network', 'map-pin', pod.host_ip or 'Host IP Unavailable', class_name='min-h-[32rem]', badge_size='detail')",
        "detail.detail_card('Pod Conditions', 'activity', pod.ready, class_name='min-h-[32rem]', badge_size='detail')",
        "detail.detail_card('Pod Configuration', 'settings-2', table_label.count_text(pod.configuration.container_count, 'Container'), class_name='min-h-[30rem]', badge_size='detail')",
    )
    for expected in expected_cards:
        assert expected in template

    assert "detail.status_row('Phase', pod.status or 'Unknown', phase_tone, none, 'detail')" in template
    assert "detail.status_row('Ready Containers', pod.ready, ready_tone, none, 'detail')" in template
    assert "detail.status_row('Security Context'" in template
    assert ", none, 'detail')" in template


def test_pod_context_values_use_semantic_detail_labels() -> None:
    template = read("app/templates/inventory/pods/partials/_pod_detail_content.html")

    expected_tones = (
        "'besteffort': 'warning'",
        "'always': 'normal'",
        "'clusterfirst': 'normal'",
    )
    for expected in expected_tones:
        assert expected in template

    assert "normalized_selector in ['kubernetes.io/os=linux', 'beta.kubernetes.io/os=linux']" in template
    assert "table_label.status_label(selector, 'normal', none, 'detail')" in template
    assert "detail.status_row('QoS Class', pod.qos_class or 'Unknown', qos_tones.get(normalized_qos_class, 'unknown'), none, 'detail')" in template
    assert "detail.status_row('Restart Policy', pod.configuration.restart_policy or 'Unknown', restart_policy_tones.get(normalized_restart_policy, 'unknown'), none, 'detail')" in template
    assert "detail.status_row('DNS Policy', pod.configuration.dns_policy or 'Unknown', dns_policy_tones.get(normalized_dns_policy, 'unknown'), none, 'detail')" in template


def test_type_columns_render_values_as_labels() -> None:
    template = read("app/templates/inventory/pods/partials/_pod_detail_content.html")

    assert "table_label.metadata_label(container.kind, none, false, 'detail')" in template
    assert "table_label.metadata_label(volume.type, none, false, 'detail')" in template
    assert '<span class="text-xs font-normal leading-5 text-content-secondary">{{ volume.type }}</span>' not in template
