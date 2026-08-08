#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCKED_TEMPLATE_PREFIXES = (
    'app/templates/welcome/',
    'app/templates/dashboards/kubernetes/',
    'app/templates/inventory/',
    'app/templates/analytics/',
    'app/templates/kubernetes_operations/',
    'app/templates/governance/',
    'app/templates/integrations/',
    'app/templates/prometheus/',
    'app/templates/alertmanager/',
)

# Shared domain components may legitimately own a tablist. Page templates may not.
SHARED_TABLIST_PREFIXES = (
    'app/templates/components/',
    'app/templates/analytics/components/',
    'app/templates/integrations/components/',
)

RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border|ring|shadow|fill|stroke)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|purple|violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
    r'\d{2,3}(?:/\d{1,3})?\b'
)
RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
ARBITRARY_TEXT = re.compile(r'\btext-\[[^\]]+\]')
INLINE_STYLE = re.compile(r'\bstyle\s*=', re.I)
INLINE_HANDLER = re.compile(r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=', re.I)
TABLIST = re.compile(r'role=["\']tablist["\']', re.I)
HEADING_UPPERCASE = re.compile(r'<(?:h[1-6]|th|label)\b[^>]*class="[^"]*\buppercase\b', re.I)
COMPACT_PILL = re.compile(r'class="(?=[^"]*\brounded-full\b)(?=[^"]*\bpx-(?:1|1\.5|2|2\.5|3)\b)[^"]*\btext-(?:xs|\[(?:9|10|11)px\])\b[^"]*"', re.I)


def locked_templates() -> list[Path]:
    paths: list[Path] = []
    for prefix in LOCKED_TEMPLATE_PREFIXES:
        base = ROOT / prefix
        if base.exists():
            paths.extend(base.rglob('*.html'))
    return sorted(set(paths))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    errors: list[str] = []
    checked = 0

    for path in locked_templates():
        checked += 1
        relative = rel(path)
        source = path.read_text(encoding='utf-8')

        if RAW_HEX.search(source):
            errors.append(f'{relative}: raw hex color is forbidden in locked workspaces')
        if RAW_PALETTE.search(source):
            errors.append(f'{relative}: raw Tailwind palette utility is forbidden in locked workspaces')
        if ARBITRARY_TEXT.search(source):
            errors.append(f'{relative}: arbitrary text size is forbidden in locked workspaces')
        if INLINE_STYLE.search(source):
            errors.append(f'{relative}: inline style is forbidden; use shared component/static utility ownership')
        if INLINE_HANDLER.search(source):
            errors.append(f'{relative}: inline DOM event handler is forbidden')
        if HEADING_UPPERCASE.search(source):
            errors.append(f'{relative}: headings/table headers/form labels must use Title Case, not uppercase utility')
        if COMPACT_PILL.search(source):
            errors.append(f'{relative}: compact labels must use rounded-md shared label geometry, not rounded-full')
        if TABLIST.search(source) and not relative.startswith(SHARED_TABLIST_PREFIXES):
            errors.append(f'{relative}: page-local tablist is forbidden; use a shared tab component')

    # Canonical detail workspaces must use shared framed tabs.
    for relative in (
        'app/templates/integrations/kubernetes/detail.html',
        'app/templates/prometheus/instance_detail.html',
        'app/templates/alertmanager/instance_detail.html',
    ):
        source = (ROOT / relative).read_text(encoding='utf-8')
        if 'components/framed_workspace_tabs.html' not in source or 'framed_workspace_tabs.render(' not in source:
            errors.append(f'{relative}: provider detail workspace must use framed_workspace_tabs')

    # Shared label geometry is a frozen rule for Integration and table surfaces.
    labels = (ROOT / 'app/templates/components/table_label.html').read_text(encoding='utf-8')
    if 'whitespace-nowrap' not in labels:
        errors.append('app/templates/components/table_label.html: compact labels must remain single-line by default')

    # Security boundary: baseline Kubernetes validation RBAC must never grant
    # cluster-wide Secrets read. A separate namespace-scoped optional Role is
    # intentionally allowed for explicitly approved governance workflows.
    rbac = (ROOT / 'app/templates/integrations/kubernetes/partials/_minimum_validation_rbac.html').read_text(encoding='utf-8')
    baseline_start = rbac.find('id="minimum-rbac-panel-baseline"')
    optional_start = rbac.find('id="minimum-rbac-panel-secret"')
    baseline_rbac = rbac[baseline_start:optional_start] if baseline_start >= 0 and optional_start > baseline_start else rbac
    if re.search(r'resources:\s*\[[^\]]*"secrets"', baseline_rbac):
        errors.append('Kubernetes baseline validation RBAC must not include cluster-wide Secrets access')
    if optional_start >= 0:
        optional_rbac = rbac[optional_start:]
        if 'kind: Role' not in optional_rbac or 'kind: RoleBinding' not in optional_rbac:
            errors.append('Optional Kubernetes Secret access must remain namespace-scoped via Role + RoleBinding')

    # Operational toast must remain script-owned and free from inline progress styles.
    toast = (ROOT / 'app/templates/components/operational_toast.html').read_text(encoding='utf-8')
    toast_js = (ROOT / 'app/static/js/operational_toasts.js').read_text(encoding='utf-8')
    if 'data-operational-toast-timer' not in toast or 'style=' in toast:
        errors.append('Operational toast timer must be markup-only with no inline style')
    if 'timerBar.animate' not in toast_js or 'scaleX(0)' not in toast_js:
        errors.append('Operational toast countdown must remain owned by operational_toasts.js')

    # Runtime presentation import required by Kubernetes Integration service.
    runtime_presentation = (ROOT / 'app/integrations/runtime/presentation.py').read_text(encoding='utf-8')
    if 'def runtime_observation_state_view(' not in runtime_presentation:
        errors.append('runtime_observation_state_view must remain available to Integration service')

    # Core obsolete compatibility paths are not allowed to return.
    obsolete = (
        'app/static/js/inventory/topology_bootstrap.js',
        'app/dashboards/kubernetes/snapshot_builder.py',
        'app/analytics/common/cache.py',
        'app/templates/inventory/components/_detail_macros.html',
        'app/kubernetes_operations/secrets/routes.py',
    )
    for relative in obsolete:
        if (ROOT / relative).exists():
            errors.append(f'Obsolete compatibility path reintroduced: {relative}')

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI core workspace UI lock passed across '
        f'{checked} templates: Welcome, Kubernetes Dashboard, Kubernetes Inventory, Analytics, Operations, Governance, '
        'and Integrations are protected against raw palette drift, arbitrary typography, inline UI debt, '
        'page-local tablists, compact pill labels, known compatibility wrappers, and RBAC regression.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
