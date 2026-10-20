"""UAT REVIEW(2): Allocation Budget dialog header and information footer."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def test_allocation_budget_header_labels_and_fixed_info_footer() -> None:
    source = (ROOT / 'app/templates/kubernetes/tenant/partials/_capacity_governance.html').read_text(encoding='utf-8')
    Environment(autoescape=True).parse(source)

    dialog = source.split('<dialog id="{{ dialog_id }}"', 1)[1].split('</dialog>', 1)[0]
    header = dialog.split('<header ', 1)[1].split('</header>', 1)[0]
    scroll_body, footer = dialog.split('<footer ', 1)

    assert 'id="{{ dialog_id }}-title"' in header
    # Screenshot #3 reference: icon then inline cluster title/state,
    # explanatory text next, and metadata chips as the final header row.
    assert 'data-lucide="chart-no-axes-combined"' in header
    assert 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-kaori-soft' in header
    assert 'flex min-w-0 flex-wrap items-center gap-2' in header
    assert header.index('{{ item.cluster.name }}') < header.index('table_label.status_label(item.state, state_tone)')
    assert header.index('table_label.status_label(item.state, state_tone)') < header.index(
        'id="{{ dialog_id }}-description"'
    )
    assert header.index('id="{{ dialog_id }}-description"') < header.index('aria-label="Allocation Budget context"')
    assert "table_label.metadata_label('Allocation Budget', icon='chart-no-axes-combined')" in header
    assert "table_label.metadata_label('Request commitment', icon='gauge')" in header
    assert 'item.cluster.environment|title' in header
    assert 'Allocation Budget</p>' not in header

    assert 'min-h-0 overflow-y-auto bg-surface-page p-4 text-left sm:p-5' in scroll_body
    assert 'capacity_budget_bars.get(item.cluster.id|string, [])' in scroll_body
    for value in ('bar.budget', 'bar.committed', 'bar.headroom'):
        assert value in scroll_body
    assert 'progress_bar.stacked_bar(bar.percent,' in scroll_body

    assert 'aria-label="Allocation Budget information footer"' in footer
    assert 'flex shrink-0 flex-col gap-2' in footer
    assert 'px-4 py-2.5 sm:flex-row' in footer
    assert 'item.committed_namespace_count' in footer
    assert 'No governed namespaces' in footer
    assert 'Storage is logical admission capacity.' in footer
    assert 'data-lucide="info"' in footer
    assert 'data-kaori-dialog-close' in footer
    assert 'aria-label="Close Allocation Budget"' in footer
    assert 'class="{{ table_ui.action_classes() }} ml-auto shrink-0"' in footer
    assert dialog.count('data-kaori-dialog-close') == 2
    assert dialog.index('</div>\n                                        <footer') > dialog.index(
        'min-h-0 overflow-y-auto'
    )
    assert 'hx-post' not in dialog
