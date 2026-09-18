from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_general_hero_uses_compact_context_without_duplicate_actions() -> None:
    hero = read('app/templates/settings/general/partials/_hero.html')
    assert 'Current Presentation' in hero
    assert 'Account Preference' in hero
    assert 'Canonical operational timestamps remain UTC' in hero
    assert 'Release Identity' in hero
    assert 'Compatibility Policy' in hero
    assert 'context_header' in hero
    assert 'context_panel_metrics_classes' in hero
    assert 'primary_action_classes' not in hero


def test_time_zone_workspace_has_clear_configuration_sequence() -> None:
    template = read('app/templates/settings/general/partials/_time_locale.html')
    page = read('app/templates/settings/general/partials/_page_content.html')
    for token in (
        'Selection Mode',
        'Browser Detection',
        'Manual Time Zone',
        'Preference Scope &amp; Boundary',
        'Presentation Scope',
        'Canonical Data',
        'External Systems',
        'Display preference only.',
        'Effective Time Zone',
        'Save Time Zone',
        'Personal Preference',
    ):
        assert token in template
    assert 'data-timezone-workspace-layout="full-width"' in page
    assert 'data-timezone-preference-boundary="inline"' in template
    assert 'general-current-time' in template
    assert 'detect-browser-timezone' in template
    assert 'pointer-events-none' in template


def test_time_zone_workspace_runtime_uses_dedicated_static_authority() -> None:
    template = read('app/templates/settings/general/partials/_time_locale.html')
    index = read('app/templates/settings/general/index.html')
    runtime = read('app/static/js/settings/time_locale.js')
    inline_baseline = read('docs/architecture/ui-inline-debt-baseline.json')

    assert '<script>' not in template
    assert 'data-timezone-workspace' in template
    assert 'data-timezone-preview-timestamp="{{ preview_timestamp }}"' in template
    assert 'data-timezone-browser-input="{{ timezone_form.browser_timezone.id }}"' in template
    assert 'data-timezone-manual-select="{{ timezone_form.timezone.id }}"' in template
    assert "js/settings/time_locale.js" in index
    assert 'app/templates/settings/general/partials/_time_locale.html' not in inline_baseline

    assert 'initTimeLocaleWorkspace' in runtime
    assert 'data-timezone-workspace' in runtime
    assert 'Intl.DateTimeFormat().resolvedOptions().timeZone' in runtime
    assert "manualSelect.tabIndex = automatic ? -1 : 0" in runtime
    assert "manualSelect.setAttribute('aria-disabled', automatic ? 'true' : 'false')" in runtime
    assert "document.body.addEventListener('htmx:afterSwap'" in runtime


def test_regional_format_is_one_full_width_workspace_with_inline_boundary() -> None:
    template = read('app/templates/settings/general/partials/_regional_format.html')
    page = read('app/templates/settings/general/partials/_page_content.html')
    for token in (
        'Format Controls',
        'Regional Locale',
        'Date Format',
        'Time Format',
        'Current Presentation Preview',
        'Preference Scope &amp; Boundary',
        'Presentation Scope',
        'Interface Language',
        'Data &amp; Execution',
        'Display preference only.',
        'Effective Format:',
        'Save Regional Format',
    ):
        assert token in template
    assert 'data-regional-format-workspace-layout="full-width"' in page
    assert 'data-regional-format-workspace="unified"' in template
    assert 'data-regional-format-controls="inline-grid"' in template
    assert 'data-regional-preference-boundary="inline"' in template
    assert 'settings/general/partials/_impact_information.html' not in page
    assert template.count('rounded-xl border border-outline-default bg-surface-subtle p-4') == 0


def test_personal_preference_boundaries_live_in_active_workspaces() -> None:
    timezone = read('app/templates/settings/general/partials/_time_locale.html')
    regional = read('app/templates/settings/general/partials/_regional_format.html')
    page = read('app/templates/settings/general/partials/_page_content.html')

    assert not (ROOT / 'app/templates/settings/general/partials/_impact_information.html').exists()
    assert 'settings/general/partials/_impact_information.html' not in page
    for source in (timezone, regional):
        assert 'Preference Scope &amp; Boundary' in source
        assert 'Presentation Scope' in source
        assert 'Display preference only.' in source


def test_system_information_is_explicitly_read_only_and_traceable() -> None:
    main = read('app/templates/settings/general/partials/_system_information.html')
    assert 'Release Identity' in main
    assert 'Read-Only Metadata' in main
    assert 'Build Reference' in main
    assert 'Build Date' in main
    assert 'Capability Catalog' in main
    assert 'Release Governance' in main
    assert 'Information Boundary' in main
    assert 'Not Exposed' in main
    assert 'data-system-information-workspace="unified"' in main
    assert 'data-system-information-visual-hierarchy="release-led"' in main
    assert 'data-system-information-workspace-layout="full-width"' in read(
        'app/templates/settings/general/partials/_page_content.html'
    )
    assert not (ROOT / 'app/templates/settings/general/partials/_system_information_context.html').exists()


def test_compatibility_workspace_keeps_version_and_readiness_decisions_separate() -> None:
    main = read('app/templates/settings/general/partials/_compatibility_versions.html')
    assert 'Integration Compatibility' in main
    assert 'Validation Required' in main
    assert 'Qualified Compatibility Matrix' in main
    assert 'upstream support calendar' in main
    assert 'item.version_scheme' in main
    assert 'Capability Validation Basis' in main
    assert 'Reading the Matrix' in main
    assert 'Minimum Compatible' in main
    assert 'Recommended Baseline' in main
    assert 'Live Readiness' in main
    assert 'Policy Boundary' in main
    assert 'data-compatibility-versions-workspace="unified"' in main
    assert 'data-compatibility-visual-hierarchy="matrix-led"' in main
    assert 'data-compatibility-versions-workspace-layout="full-width"' in read(
        'app/templates/settings/general/partials/_page_content.html'
    )
    assert not (ROOT / 'app/templates/settings/general/partials/_compatibility_versions_context.html').exists()
