import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_source_unknown_scope_persists_across_modal_actions() -> None:
    template = (ROOT / 'app/templates/intelligence/partials/_alert_ops_case_workspace.html').read_text(encoding='utf-8')
    # The hidden field is part of the same mutation context even after djLint multiline formatting.
    assert re.search(
        r'<input\\b(?=[^>]*\\btype="hidden")(?=[^>]*\\bname="source_state")'
        r'(?=[^>]*\\bvalue="\\{\\{ payload\\.filters\\.source_state \\}\\}")[^>]*>',
        template,
        flags=re.DOTALL,
    )
    assert 'name="severity" value="{{ payload.filters.severity }}"' in template
    assert 'name="domain" value="{{ payload.domain }}"' in template


def test_source_unknown_shortcut_has_matching_link_and_htmx_target() -> None:
    template = (ROOT / 'app/templates/intelligence/partials/_alert_ops_active.html').read_text(encoding='utf-8')
    assert template.count("source_state='unknown'") == 2
    assert "severity='unknown')" not in template
