"""Compilation guard for Data Lifecycle page templates (#2967).

A malformed Jinja closer in the shared policy partial can block all nine
Retention Policies routes. Parse the actual files, not substrings or counts
of if/endif markers, so syntax errors cannot pass a source-only contract.
"""

from pathlib import Path

import pytest
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ROOT = ROOT / 'app/templates/platform_operations/data_lifecycle'
PAGE_TEMPLATES = (
    'index.html',
    'partials/_domain_workspace.html',
    'partials/_history.html',
    'partials/_storage.html',
)


@pytest.mark.parametrize('relative_path', PAGE_TEMPLATES)
def test_data_lifecycle_templates_parse_with_real_jinja_parser(relative_path: str) -> None:
    source_path = TEMPLATE_ROOT / relative_path
    source = source_path.read_text(encoding='utf-8')
    # Parsing the complete template catches malformed block delimiters
    # even when a previous substring-count assertion would pass.
    Environment().parse(source, name=f'platform_operations/data_lifecycle/{relative_path}')


def test_notification_delivery_block_is_closed_before_audit_event_branch() -> None:
    source = (TEMPLATE_ROOT / 'partials/_domain_workspace.html').read_text(encoding='utf-8')
    assert (
        "{% if selected.name == 'notification_delivery' %}\n"
        '            <p class="rounded-lg border border-outline-subtle '
    ) in source
    assert (
        "No per-record archive search.\n"
        "            </p>\n"
        "        {% endif %}\n"
        "        {% if selected.name == 'audit_event' %}"
    ) in source
    assert '{% endif %>' not in source
    assert "Manual Archive Only enabled" in source
