from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_inventory_pagination_copy_uses_resource_aware_title_case():
    cluster = read('app/templates/inventory/overview/partials/_resources_by_cluster_content.html')
    namespace = read('app/templates/inventory/namespaces/partials/_table_content.html')
    assert "'Cluster' if" in cluster and "'Clusters'" in cluster
    assert "pagination_ui.resource_name('Namespaces', pagination.total_items)|trim" in namespace
    assert '>Rows</label>' in namespace


def test_namespace_summary_uses_control_posture_and_sentence_case_descriptions():
    template = read('app/templates/inventory/namespaces/partials/_summary_cards.html')
    assert 'Namespace Control Posture' in template
    assert 'resource-control, and security evidence' in template
    for label in (
        'ResourceQuota Configured',
        'LimitRange Configured',
        'NetworkPolicy Configured',
        'PSA Enforce Explicitly Set',
        'Missing Default ServiceAccount',
        'Lifecycle Exceptions',
    ):
        assert label in template
    assert 'Available For Workload Placement' not in template


def test_expandable_rows_use_deterministic_fetch_request_flow():
    macro = read('app/templates/components/details/_expandable_row.html')
    script = read('app/static/js/detail_rows.js')
    assert 'data-detail-url="{{ detail_url or' in macro
    assert 'event.stopImmediatePropagation()' not in script
    assert 'fetch(detailUrl' in script
    assert "credentials: 'same-origin'" in script
    assert "'HX-Request': 'true'" in script
    assert 'renderLoading(target, button)' in script
    assert 'button?.dataset.detailContext' in script
    assert "target.dataset.open = 'true'" in script
    assert 'window.htmx?.process' in script
    assert 'hx-get="{{ detail_url }}"' not in macro
