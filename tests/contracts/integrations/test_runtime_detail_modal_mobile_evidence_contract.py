"""Source contract for readable, untruncated integration evidence on mobile."""

from pathlib import Path


MODAL = (
    Path(__file__).resolve().parents[3]
    / "app/templates/integrations/components/_record_detail_modal.html"
)


def test_detail_dialog_keeps_evidence_readable_on_narrow_viewports():
    template = MODAL.read_text(encoding="utf-8")

    # Long diagnostic keys must wrap instead of being clipped by dialog overflow.
    assert 'bg-surface-page px-4 py-5 [overflow-wrap:anywhere] sm:px-6' in template
    assert 'overflow-x-hidden overflow-y-auto' in template

    # The persisted-evidence boundary must remain visible at mobile widths.
    assert 'class="hidden text-xs leading-5 text-content-muted sm:block"' not in template
    assert 'class="min-w-0 flex-1 break-words text-xs leading-5 text-content-muted [overflow-wrap:anywhere]"' in template
    assert "{{ footer_text }}" in template
    assert 'method="dialog"' in template
