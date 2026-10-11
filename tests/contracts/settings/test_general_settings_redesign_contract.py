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
    hero = read('app/templates/settings/general/partials/_hero.html')
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
    assert 'general-current-time' in hero
    assert 'detect-browser-timezone' in template


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
    assert 'js/settings/time_locale.js' in index
    assert 'app/templates/settings/general/partials/_time_locale.html' not in inline_baseline

    assert 'initTimeLocaleWorkspace' in runtime
    assert 'data-timezone-workspace' in runtime
    assert 'Intl.DateTimeFormat().resolvedOptions().timeZone' in runtime
    assert "manualPanel?.classList.toggle('pointer-events-none', automatic)" in runtime
    assert 'manualSelect.tabIndex = automatic ? -1 : 0' in runtime
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
    assert 'Formats regional labels and dates; interface language stays unchanged.' in template
    assert 'Sets the date format across KAORI views and reports.' in template
    assert 'Sets regional month labels and formatting conventions.' not in template
    assert 'Used for inventory, governance, reports, activity' not in template
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
    assert 'data-system-build-evidence="runtime-config"' in main
    assert "system_information.build_sha == 'Not provided'" in main
    assert "system_information.build_date == 'Not provided'" in main
    assert "table_label.status_label('Incomplete', 'warning')" in main
    assert 'artifact lineage cannot be verified here' in main
    assert 'Product Release Focus' in main
    assert 'not a live provider-readiness check' in main
    assert 'runtime provider readiness and RBAC determine availability' in main
    assert 'open:bg-surface-hover' in main
    assert 'open:bg-surface-subtle' not in main
    assert 'for highlight in system_information.release_highlights' in main
    assert 'for group in system_information.feature_groups' in main
    assert 'for feature in group.features' in main
    assert '<details' in main
    assert '<summary' in main
    assert 'lg:grid-cols-3' in main
    assert 'border-brand-outline' in main
    assert 'data-system-information-workspace-layout="full-width"' in read(
        'app/templates/settings/general/partials/_page_content.html'
    )
    assert not (ROOT / 'app/templates/settings/general/partials/_system_information_context.html').exists()


def test_compatibility_workspace_keeps_policy_contract_qualification_and_readiness_separate() -> None:
    main = read('app/templates/settings/general/partials/_compatibility_versions.html')
    assert 'Integration Compatibility' in main
    assert 'Capability Evidence Required' in main
    assert 'Compatibility Qualification Matrix' in main
    assert 'Annual five-year lifecycle policy' in main
    assert 'item.version_scheme' in main
    assert 'Lifecycle Policy' in main
    assert 'Support Window' in main
    assert 'General Contracts' in main
    assert 'Qualification Rows' in main
    assert 'Reading the Matrix' in main
    assert 'Annual Lifecycle' in main
    assert 'General Contract' in main
    assert 'Version Qualification' in main
    assert 'Qualified Versions' in main
    assert 'Upstream Lifecycle' in main
    assert 'KAORI Support' in main
    assert 'Readiness Authority' in main
    assert 'Live Readiness' in main
    assert 'Policy Boundary' in main
    assert 'Contract Ownership' in main
    assert 'data-compatibility-versions-workspace="unified"' in main
    assert 'data-compatibility-visual-hierarchy="contract-led"' in main
    assert 'data-compatibility-versions-workspace-layout="full-width"' in read(
        'app/templates/settings/general/partials/_page_content.html'
    )
    assert not (ROOT / 'app/templates/settings/general/partials/_compatibility_versions_context.html').exists()


def test_browser_timezone_redetection_reuses_canonical_operational_toast_without_persistence() -> None:
    template = read('app/templates/settings/general/partials/_time_locale.html')
    runtime = read('app/static/js/settings/time_locale.js')
    toast_template = read('app/templates/components/operational_toast.html')
    toast_runtime = read('app/static/js/operational_toasts.js')
    settings_docs = read('app/settings/README.md')

    assert 'data-timezone-detection-toast="success"' in template
    assert 'data-timezone-detection-toast="error"' in template
    assert template.count('{% include "components/operational_toast.html" %}') == 2
    assert "feedback_id='settings-browser-timezone-detection'" in template
    assert 'data-operational-toast-message' in toast_template
    assert 'window.showOperationalToast = (toast) =>' in toast_runtime
    assert 'initialiseToast(toast)' in toast_runtime
    assert "window.showOperationalToast?.(toast)" in runtime
    assert "if (messageNode) messageNode.textContent = message" in runtime
    assert "'Browser timezone unavailable'" in runtime
    assert "if (!timezone)" in runtime
    assert "const unchanged = timezone === previousTimezone" in runtime
    assert 'No preference was saved.' in runtime
    assert "detectButton?.addEventListener('click', () => {" in runtime
    assert "        detect()\n        syncMode()" in runtime
    assert "fetch(" not in runtime
    assert "kaori:notifications-changed" not in runtime
    assert "Activity Audit" not in runtime
    assert 'Detect Again' in settings_docs
