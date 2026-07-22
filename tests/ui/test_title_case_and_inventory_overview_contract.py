from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_overview_initializes_row_context_before_use():
    template = (ROOT / "app/templates/inventory/overview/partials/_resources_by_cluster_content.html").read_text()

    summary_set = "{% set summary = overview.inventory_summary.get(cluster.id, {}) %}"
    synced_set = "{% set synced_at = summary.get('synced_at') %}"
    row_open = '<tr class="transition hover:bg-surface-hover">'
    first_cell = '<td class="px-5 py-3.5">'
    summary_use = "{{ summary.get('namespaces', 0) }}"

    assert summary_set in template
    assert synced_set in template
    assert row_open in template
    assert first_cell in template
    assert template.index(summary_set) < template.index(summary_use)
    assert template.index(synced_set) < template.index("{% if synced_at %}")
