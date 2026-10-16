"""Regression contracts for the user-approved KAORI command-first setup redesign.

This remains a source-level contract; real rendered Visual QA is a separate gate.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/access/authentication/setup_required.html'
FLOW = ROOT / 'app/templates/components/operational_flow_steps.html'
SHELL = ROOT / 'app/templates/components/operational_section_card.html'
AUTH_LOCK = ROOT / 'docs/design/KAORI_AUTHENTICATION_SURFACE_LOCK_V1.md'
VERIFIER = ROOT / 'scripts/verify_authentication_surface_final_lock.py'


def test_rejected_nested_card_frame_and_equal_width_sidebar_are_absent() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')

    assert 'data-kaori-setup-workspace="release-v4"' in source
    assert 'data-kaori-setup-design="command-first"' in source
    assert 'data-kaori-setup-outer-frame' not in source
    assert 'data-kaori-setup-identity-card' not in source
    assert 'data-kaori-setup-bootstrap-card' not in source
    assert 'lg:col-span-2' not in source
    assert 'grid items-stretch gap-3 lg:grid-cols-3' not in source
    assert 'rounded-2xl border border-kaori-outline bg-surface-hover' not in source
    assert 'data-kaori-setup-primary-action' in source
    assert 'data-kaori-setup-readiness-strip' in source
    assert 'data-kaori-setup-security' in source
    assert 'data-kaori-setup-flow' in source


def test_one_primary_action_has_hierarchy_and_shared_clipboard_terminal() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    shell = SHELL.read_text(encoding='utf-8')

    assert 'Primary action · One-time setup' in source
    assert 'Run Initial Database Bootstrap' in source
    assert 'text-lg font-semibold leading-6 text-content-primary' in source
    assert 'border-l-4 border-kaori-primary' not in source
    assert "operational_section_card.shell_classes('mt-4')" in source
    assert "macro shell_classes(extra_classes='')" in shell
    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' in shell
    assert 'data-kaori-setup-command' in source
    assert 'terminal_command.render(bootstrap_command' in source
    assert "copy_label='Copy Command'" in source
    assert "copy_label='Copy Command', compact=true" in source
    assert ('docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap') in source
    assert 'Windows PowerShell' in source
    assert "config.get('APP_ENV') == 'development'" in source


def test_steps_are_unboxed_and_existing_component_boxed_default_survives() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    shared = FLOW.read_text(encoding='utf-8')

    assert 'operational_flow_steps.render(initialization_flow_rows' in source
    assert "variant='inline'" in source
    assert 'Run the Initial KAORI Database Bootstrap' in source
    assert 'border-l-2 border-outline-default' in shared
    assert "variant == 'inline'" in shared
    assert "variant='boxed'" in shared
    assert 'bg-surface-card p-3' in shared
    assert 'role="listitem"' in shared
    assert 'sm:grid-cols-3' in shared


def test_semantic_safety_readiness_and_advanced_remain_fail_closed() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')

    assert source.count('<h1 ') == 1
    assert 'aria-labelledby="setup-required-title"' in source
    assert 'data-kaori-auth-setup-heading-authority="readiness-workspace"' in source
    assert 'readiness.setup_required' in source
    assert "table_label.status_indicator_label('Reachable', 'normal')" in source
    assert "table_label.status_indicator_label('Not Installed', 'warning')" in source
    assert "table_label.status_indicator_label('Unavailable', 'critical')" in source
    assert 'operational_callout.render("Encryption Key Requirement"' in source
    assert 'operational_callout.render("PostgreSQL Is Unavailable"' in source
    assert 'variant="semantic"' in source
    assert 'INTEGRATION_CREDENTIAL_KEY' in source
    assert 'view_more_content.render(' in source
    assert 'open_by_default=true' not in source
    assert 'Manual Initialization Commands' in source
    assert 'Missing Schema Objects' in source
    assert "section_link_button.render(url_for('auth.login')" in source
    assert 'This readiness workspace is read-only.' in source
    assert 'db.session.' not in source
    assert 'style="' not in source


def test_authentication_design_authority_and_existing_verifier_are_updated() -> None:
    doc = AUTH_LOCK.read_text(encoding='utf-8')
    verifier = VERIFIER.read_text(encoding='utf-8')

    assert 'full\ncommand-first redesign' in doc
    assert 'REJECTED' in doc
    assert 'one primary action panel' in doc.lower()
    assert 'operational_flow_steps.render(..., variant=' in doc
    assert 'data-kaori-setup-design="command-first"' in verifier
    assert "data-kaori-setup-outer-frame' not in setup" in verifier
    assert "variant='inline'" in verifier


def test_normal_zoom_has_one_light_canvas_without_rejected_heavy_frame() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    shell = SHELL.read_text(encoding='utf-8')
    doc = AUTH_LOCK.read_text(encoding='utf-8')

    # One quiet surface for content readability at default 100% zoom.
    assert source.count('data-kaori-setup-canvas="light"') == 1
    assert 'max-w-4xl rounded-xl border border-outline-subtle bg-surface-card' in source
    assert 'px-4 py-4 shadow-sm sm:px-5 sm:py-5 lg:px-6' in source
    assert 'bg-surface-page px-3 py-3 sm:px-4 sm:py-4' in source
    assert source.index('data-kaori-setup-canvas="light"') < source.index('data-kaori-setup-readiness-strip')
    # The inline rail and warning do not become more peer cards.
    assert 'data-kaori-setup-identity-card' not in source
    assert 'data-kaori-setup-outer-frame' not in source
    assert 'lg:col-span-2' not in source
    assert "operational_section_card.shell_classes('mt-4')" in source
    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' in shell
    assert 'neutral white content surface' in doc


def test_requested_copy_is_shorter_without_changing_bootstrap_semantics() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')

    assert 'PostgreSQL is ready. Run setup to enable sign-in and background jobs.' in source
    assert 'Preserve INTEGRATION_CREDENTIAL_KEY.' in source
    assert 'Verify INTEGRATION_CREDENTIAL_KEY before bootstrap.' in source
    assert 'PostgreSQL is connected. Complete the one-time database setup' not in source
    assert 'Check INTEGRATION_CREDENTIAL_KEY; keep it unchanged.' not in source
    assert 'Windows PowerShell · Repository Root' in source
    assert 'terminal_command.render(bootstrap_command' in source


def test_native_browser_zoom_uses_compact_layout_without_css_scaling() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    shell = SHELL.read_text(encoding='utf-8')
    authority = AUTH_LOCK.read_text(encoding='utf-8')

    assert 'max-w-4xl' in source
    assert 'max-w-6xl' not in source
    assert 'mt-3 grid gap-x-4 gap-y-2' in source
    assert "operational_section_card.shell_classes('mt-4')" in source
    assert "operational_section_card.shell_classes('mt-4 p-4 sm:p-5')" in source
    assert 'border-l-4 border-kaori-primary' not in source
    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' in shell
    assert 'mt-3" data-kaori-setup-command' in source
    assert '<section class="mt-5"' in source
    assert 'data-kaori-setup-flow' in source
    assert 'aria-labelledby="initialization-path-title"' in source
    assert 'mt-4" data-kaori-setup-advanced' in source
    assert 'mt-4 flex flex-col gap-2 border-t' in source
    assert 'Run once in Windows PowerShell at the repo root to create the schema, grants, and admin.' in source
    assert 'text-xs leading-5 text-content-muted' in source
    assert 'max-w-4xl' in authority
    assert 'never set CSS zoom/transform scaling' in authority
    assert 'zoom:' not in source
    assert 'transform: scale' not in source


def test_small_viewport_retains_readable_and_copyable_bootstrap() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    assert 'w-full max-w-4xl' in source
    assert 'sm:grid-cols-3' in source
    assert 'flex flex-col gap-2 sm:flex-row' in source
    assert "copy_label='Copy Command', compact=true" in source
    assert 'data-kaori-setup-security' in source
    assert 'data-kaori-setup-advanced' in source
    assert 'data-kaori-setup-primary-action' in source
