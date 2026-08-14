from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_about_menu_is_immediately_above_logout_and_opens_dialog() -> None:
    navbar = read('app/templates/components/navigation/navbar.html')

    about_index = navbar.index('<span class="flex-1">About</span>')
    logout_index = navbar.index('<span>Logout</span>')

    assert about_index < logout_index
    assert '@click="openAbout()"' in navbar
    assert 'aria-controls="kaori-about-dialog"' in navbar
    assert '<template x-teleport="body">' in navbar
    assert '{% include "components/navigation/_about_modal.html" %}' in navbar


def test_about_modal_uses_safe_release_metadata_and_canonical_system_information_link() -> None:
    modal = read('app/templates/components/navigation/_about_modal.html')

    assert 'id="kaori-about-dialog"' in modal
    assert 'role="dialog"' in modal
    assert 'aria-modal="true"' in modal
    assert 'class="fixed inset-0 z-[90] overflow-y-auto"' in modal
    assert 'class="relative flex min-h-full items-center justify-center p-4 sm:p-6"' in modal
    assert 'flex w-full max-w-2xl flex-col overflow-hidden' in modal
    assert 'max-h-[calc(100dvh-2rem)]' in modal
    assert 'min-h-0 space-y-4 overflow-y-auto' in modal
    assert "config.get('APP_VERSION', 'Unknown')" in modal
    assert "config.get('APP_ENV', 'development')" in modal
    assert 'Knowledge, Automation, Operations, Resilience &amp; Intelligence.' in modal
    assert 'sm:whitespace-nowrap' in modal
    assert "current_user.has_permission('system.view')" in modal
    assert "url_for('settings.general', tab='system-information')" in modal
    assert 'System Information' in modal
    assert 'APP_BUILD_SHA' not in modal
    assert 'APP_BUILD_DATE' not in modal
