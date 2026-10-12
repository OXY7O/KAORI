"""Database Setup Required visual boundaries — accepted #744 operator feedback.

Static source contract; browser Visual QA at desktop/mobile remains a human gate.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/access/authentication/setup_required.html'


def test_readiness_workspace_uses_compact_separate_violet_card_surfaces() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')

    assert 'data-kaori-setup-workspace="release-v4"' in source
    assert 'data-kaori-setup-identity-card' in source
    assert 'data-kaori-setup-readiness-strip' in source
    assert 'data-kaori-setup-bootstrap-card' in source
    assert 'data-kaori-setup-flow' in source

    assert source.count('data-kaori-setup-bootstrap-card') == 2
    for anchor in (
        'data-kaori-setup-identity-card',
        'data-kaori-setup-readiness-strip',
        'data-kaori-setup-flow',
    ):
        preceding = source[: source.index(anchor)]
        card = preceding.rsplit('class="', 1)[-1].split('"', 1)[0]
        assert 'rounded-xl' in card
        assert 'border-outline-default' in card
        assert 'bg-surface-' in card
        assert 'shadow-sm' in card

    # No giant parent shell or duplicate readiness row; use existing Violet tokens.
    assert 'components/operational_section_card.html' not in source
    assert 'data-kaori-setup-readiness-summary' not in source
    assert 'border-status-warning-border' not in source
    assert 'bg-[#' not in source


def test_setup_bootstrap_guidance_matches_windows_host_without_mutations() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')

    assert 'Windows PowerShell host terminal' in source
    assert 'Host Terminal · DevContainer Bootstrap' in source
    assert 'WSL Host' not in source
    assert 'WSL host' not in source
    assert 'docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap' in source
    assert "config.get('APP_ENV') == 'development'" in source
    assert "config.get('TESTING', false)" in source

    assert 'terminal_command.render(bootstrap_command' in source
    assert "copy_label='Copy Command'" in source
    assert 'compact=true' in source
    assert 'Run the Initial KAORI Database Bootstrap' in source
    assert 'The KAORI schema has not been installed yet.' in source
    assert "table_label.status_indicator_label('Not Installed', 'warning')" in source
    assert "table_label.status_indicator_label('Unavailable', 'critical')" in source


def test_security_accessibility_unavailable_and_advanced_contracts_survive() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')

    assert source.count('<h1 ') == 1
    assert 'aria-labelledby="setup-required-title"' in source
    assert 'data-kaori-auth-setup-heading-authority="readiness-workspace"' in source
    assert 'operational_callout.render("Encryption Key Requirement"' in source
    assert 'tone="warning"' in source
    assert 'variant="semantic"' in source
    assert 'INTEGRATION_CREDENTIAL_KEY' in source
    assert "readiness.setup_required" in source
    assert 'operational_callout.render("PostgreSQL Is Unavailable"' in source
    assert "database_checks, label='Database Connectivity'" in source
    assert 'operational_flow_steps.render(' in source
    assert 'view_more_content.render(' in source
    assert 'open_by_default=true' not in source
    assert 'Manual Initialization Commands' in source
    assert 'Missing Schema Objects' in source
    assert "section_link_button.render(url_for('auth.login')" in source
    assert 'This readiness workspace is read-only.' in source
