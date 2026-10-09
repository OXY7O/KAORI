"""Empty operational registries keep canonical pagination controls visible."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from app.common.pagination import build_pagination_window, pagination_payload

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'

# These are the active operational consumers where an empty-total guard
# previously hid the canonical pagination footer during local human review.
CORRECTED_REGISTRIES = (
    'integrations/delivery/notification_channels/partials/_channels_workspace.html',
    'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_binding_registry.html',
    'integrations/registry/providers/harbor/partials/_binding_registry.html',
    'integrations/storage/object_storage/providers/minio/partials/_binding_registry.html',
    'integrations/partials/_domain_workspace.html',
    'intelligence/partials/_alert_ops_history.html',
    'kubernetes/tenant/partials/_access_grant_registry.html',
    'kubernetes/tenant/partials/_credential_registry.html',
    'kubernetes/tenant/partials/_group_registry.html',
    'kubernetes/tenant/partials/_membership_registry.html',
    'kubernetes/tenant/partials/_namespace_access_registry.html',
    'kubernetes/tenant/partials/_namespace_registry.html',
    'kubernetes/tenant/partials/_operations_access_reconciliation_registry.html',
    'kubernetes/tenant/partials/_operations_drift_registry.html',
    'kubernetes/tenant/partials/_operations_evidence_registry.html',
    'kubernetes/tenant/partials/_operations_namespace_registry.html',
    'kubernetes/tenant/partials/_operations_provider_registry.html',
    'kubernetes/tenant/partials/_resource_profile_registry.html',
    'kubernetes/tenant/partials/_tenant_registry.html',
)
CONTROL_TAGS = re.compile(r'{%[-+]?\s*(if|endif)\b(.*?)[-+]?%}', re.DOTALL)
FOOTER_TOKENS = re.compile(
    r'(?:\b(?:registry|registry_ui|table_registry)\.footer\s*\(|'
    r'\bpagination_footer\s*\(|<footer\b[^>]*pagination_ui\.footer_classes)',
    re.DOTALL,
)


def test_empty_results_keep_kaori_canonical_pagination_contract() -> None:
    standard = (ROOT / 'docs/design/components/PAGINATION.md').read_text(encoding='utf-8')
    table_standard = (ROOT / 'docs/design/components/TABLE_AND_LABEL.md').read_text(encoding='utf-8')
    assert 'Showing 0–0 of 0' in standard
    assert 'Empty results remain explicit' in standard
    assert '6. Pagination footer.' in table_standard

    window = build_pagination_window(total_items=0, page=9, per_page=5)
    assert window.page == window.total_pages == 1
    assert window.start_item == window.end_item == 0
    assert window.has_prev is False and window.has_next is False
    assert tuple(pagination_payload(window)['allowed_per_page']) == (5, 10, 25, 50)


def test_shared_registry_footer_renders_for_empty_results() -> None:
    environment = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    environment.globals['url_for'] = lambda endpoint, **params: '/test/registry'
    environment.globals['request'] = SimpleNamespace(
        endpoint='test.registry',
        view_args={},
        args=SimpleNamespace(to_dict=lambda: {}),
    )
    component = environment.get_template('components/table_registry.html').module
    page = pagination_payload(build_pagination_window(total_items=0))

    html = str(
        component.footer(
            'test.registry',
            'test-registry',
            'test-registry-loading',
            page,
            {},
            [5, 10, 25, 50],
            resource_label='Access Grants',
            page_param='grant_page',
            per_page_param='grant_per_page',
        )
    )
    assert re.search(r'Showing\s+0–0\s+of\s+0\s+Access Grants', html)
    assert html.count('aria-disabled="true"') == 2
    assert 'aria-current="page">1</span>' in html
    for size in (5, 10, 25, 50):
        assert f'<option value="{size}"' in html


def test_affected_operational_registry_footers_are_unconditional() -> None:
    for relative in CORRECTED_REGISTRIES:
        source = (TEMPLATES / relative).read_text(encoding='utf-8')
        assert '.total_items > 0 %}' not in source, relative
        assert FOOTER_TOKENS.search(source), relative


def test_no_kaori_template_hides_a_pagination_footer_when_empty() -> None:
    """Scan every Jinja template; do not silently suppress a pagination footer.

    Conditional dashboards without operational pagination are unaffected.
    """
    violations: list[str] = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        stack: list[tuple[str, int]] = []
        for match in CONTROL_TAGS.finditer(source):
            kind, expression = match.group(1), match.group(2).strip()
            if kind == 'if':
                stack.append((expression, match.end()))
            elif stack:
                condition, start = stack.pop()
                if re.search(r'\.total_items\s*>\s*0\b', condition) and FOOTER_TOKENS.search(
                    source[start : match.start()]
                ):
                    violations.append(str(path.relative_to(ROOT)))

    assert not violations, 'Pagination footers hidden when empty: ' + ', '.join(violations)
