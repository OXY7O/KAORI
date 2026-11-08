from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = (
    ROOT / 'app' / 'templates' / 'access' / 'identity_providers' / 'partials' / '_directory_provisioning_strip.html'
)
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'


def test_directory_provisioning_strip_uses_shared_surface_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    # The approved strip is embedded in its parent workspace; it reuses table
    # primitives for the heading/actions without introducing another card shell.
    assert '{% import "components/table.html" as table_ui %}' in source
    assert '<section class="min-w-0"' in source
    assert 'aria-label="Directory Provisioning overview"' in source
    assert 'data-kaori-idp-directory-workspace' in source
    assert 'table_ui.block_title_classes()' in source
    assert 'table_ui.block_description_classes()' in source
    assert 'table_ui.action_classes()' in source
    assert COPIED_SHELL not in source

    assert 'Directory Provisioning' in source
    assert 'Directory Providers' in source
    assert 'Identity Links' in source
    assert 'Authorization Owner' in source
    assert "current_user.has_permission('identity_providers.provision')" in source
    assert '{% if not can_provision %}' in source
    assert '{% if can_provision %}' in source
    assert 'identity_providers.directory_provisioning' in source
    assert 'Open Directory Provisioning' in source
    assert 'Read Only' in source
    assert 'lg:grid-cols-3' in source
    assert 'summary.directory_identity_links' in source
    assert 'data-kaori-idp-directory-guardrail' in source


def test_directory_provisioning_strip_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
