"""UAT REVIEW(1): Tenant Contributions dialog header and compact footer."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def test_contributions_header_labels_and_footer_close_contract() -> None:
    source = (
        ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html'
    ).read_text(encoding='utf-8')
    Environment(autoescape=True).parse(source)

    dialog = source.split('<dialog id="{{ contributions_dialog_id }}"', 1)[1].split(
        '</dialog>', 1
    )[0]
    header = dialog.split('<header ', 1)[1].split('</header>', 1)[0]
    footer = dialog.split('<footer ', 1)[1].split('</footer>', 1)[0]

    assert 'id="{{ contributions_dialog_id }}-title"' in header
    # Screenshot #3 reference: icon, inline title/status, description,
    # then contextual metadata and right-aligned registry navigation.
    assert 'data-lucide="users-round"' in header
    assert 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-kaori-soft' in header
    assert 'flex min-w-0 flex-wrap items-center gap-2' in header
    assert header.index('Tenant Contributions</h2>') < header.index("status_label('Read-only', 'info')")
    assert header.index("status_label('Read-only', 'info')") < header.index('id="{{ contributions_dialog_id }}-description"')
    assert header.index('id="{{ contributions_dialog_id }}-description"') < header.index('aria-label="Tenant Contributions context"')
    assert "table_label.metadata_label('Committed scope', icon='layers-3')" in header
    assert "table_label.metadata_label((allocation_overview.cluster.name ~ ' · ' ~ (allocation_overview.cluster.environment|title)), icon='server', wrap=true)" in header
    assert 'Governed Namespace requests; Capsule shared quota counted once per Tenant.' in header
    assert 'Tenant Registry' in header
    assert 'Committed Allocation Evidence</p>' not in header

    assert 'aria-label="Tenant Contributions evidence footer"' in dialog
    assert 'px-4 py-2.5 sm:px-6' in footer
    assert 'Read-only committed allocation evidence' in footer
    assert 'data-kaori-dialog-close' in footer
    assert 'class="{{ table_ui.action_classes() }} shrink-0"' in footer
    assert 'aria-label="Close Tenant Contributions"' in footer
    assert 'Close' in footer
    assert 'allocation_tenant_matches }} of {{ allocation_tenant_total }} Tenants' not in footer

    # Existing header icon close and new footer close both remain functional,
    # and the canonical scroll-only, search-owned count stays intact.
    assert dialog.count('data-kaori-dialog-close') == 2
    assert 'hx-target="#{{ contributions_body_id }}"' in dialog
    assert 'hx-select="#{{ contributions_body_id }}"' in dialog
    assert 'hx-swap="outerHTML"' in dialog
    assert 'allocation_tenant_matches }} matching Tenant' in dialog
    assert 'overflow-y-auto overscroll-contain' in dialog
    assert 'allocation_tenant_rows' in dialog
    assert 'allocation_tenant_pagination' not in dialog
