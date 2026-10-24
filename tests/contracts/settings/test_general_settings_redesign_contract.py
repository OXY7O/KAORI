import re
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
    assert "table_label.status_label('Not supplied', 'unknown')" in main
    assert 'build_metadata_missing' in main
    assert 'artifact lineage cannot be verified here' in main
    assert "table_label.metadata_label('Supplied', 'git-commit-horizontal')" in main
    assert "table_label.status_label('Incomplete', 'warning')" not in main
    assert 'text-status-warning-text' not in main
    assert re.search(
        r'<section class="border-b border-outline-default bg-surface-card"\s+aria-labelledby="release-focus-heading">',
        main,
    )
    assert 'bg-surface-muted/40' not in main
    assert 'lg:divide-x lg:divide-outline-subtle' in main
    assert 'lg:divide-x lg:divide-outline-default' in main
    assert 'shadow-sm' not in main
    assert 'Release Governance' in main
    assert 'Product Release Focus' in main
    assert 'not a live provider-readiness check' in main
    assert 'runtime provider readiness and RBAC determine availability' in main
    assert 'open:bg-surface-hover' in main
    assert 'open:bg-surface-subtle' not in main
    assert 'for highlight in system_information.release_highlights' in main
    source = read('app/settings/system_information.py')
    assert 'Kubernetes, metrics, alerts and MinIO have clear ownership.' in source
    assert 'Shared evidence for jobs, delivery, and analytics.' in source
    assert 'Release tracing, identity, runtime safety and testing.' in source
    assert 'for group in system_information.feature_groups' in main
    assert 'for feature in group.features' in main
    assert '<details' in main
    assert '<summary' in main
    assert 'lg:grid-cols-3' in main
    assert 'border-t border-outline-subtle pt-5' in main
    assert 'rounded-xl border border-brand-outline' not in main
    assert 'data-system-information-workspace-layout="full-width"' in read(
        'app/templates/settings/general/partials/_page_content.html'
    )
    assert not (ROOT / 'app/templates/settings/general/partials/_system_information_context.html').exists()


def test_compatibility_workspace_keeps_policy_contract_qualification_and_readiness_separate() -> None:
    main = read('app/templates/settings/general/partials/_compatibility_versions.html')
    registry = read('app/templates/settings/general/partials/_compatibility_registry.html')
    results = read('app/templates/settings/general/partials/_compatibility_registry_results.html')
    routes = read('app/settings/routes.py')
    projection = read('app/settings/general/compatibility_registry.py')

    assert 'Integration Compatibility' in main
    assert 'Capability Evidence Required' in main
    assert 'Lifecycle Policy' in main
    assert 'Support Window' in main
    assert 'General Contracts' in main
    assert 'Qualification Rows' in main
    assert 'Reading the Matrix' in main
    assert 'Annual Lifecycle' in main
    assert 'General Contract' in main
    assert 'Version Qualification' in main
    assert 'Live Readiness' in main
    assert 'Policy Boundary' in main
    assert 'Blocking Rule' in main
    assert 'data-compatibility-versions-workspace="unified"' in main
    assert 'data-compatibility-visual-hierarchy="registry-detail"' in main
    assert 'data-compatibility-policy-summary="compact"' in main
    assert 'data-compatibility-policy-reference="disclosure"' in main
    assert 'data-compatibility-policy-toggle="accessible"' in main
    assert 'data-compatibility-policy-layout="structured-reference"' in main
    assert 'data-compatibility-policy-guide="numbered"' in main
    assert '{% include "settings/general/partials/_compatibility_registry.html" %}' in main
    assert 'bg-surface-subtle' not in main

    assert 'data-compatibility-registry="server-paginated"' in registry
    assert '{% include "settings/general/partials/_compatibility_registry_results.html" %}' in registry
    assert 'name="compatibility_search"' in registry
    assert 'name="compatibility_support"' in registry
    assert 'name="tab" value="compatibility-versions"' in registry
    assert "input changed delay:450ms from:input[name='compatibility_search']" in registry
    assert "change from:select[name='compatibility_support']" in registry
    assert 'hx-target="#compatibility-registry-results"' in registry
    assert 'hx-swap="outerHTML"' in registry
    assert 'hx-push-url="true"' in registry
    assert 'hx-sync="#compatibility-registry-results:replace"' in registry
    assert 'method="get"' in registry
    assert "url_for('settings.general')" in registry
    assert re.search(r'<noscript>\s*<button type="submit"', registry)
    assert '>Apply\n' not in registry
    assert 'hx-target="#general-settings-page"' in registry
    assert 'Reset</a>' in registry
    assert 'data-compatibility-product-detail=' not in registry

    assert "compatibility_registry.page_size ~ ' per page'" in registry
    assert 'compatibility_registry.total ~' not in registry
    assert '{% import "components/table_label.html" as table_label %}' in results
    assert 'id="compatibility-registry-results"' in results
    assert 'data-compatibility-registry-results="partial"' in results
    assert 'data-compatibility-registry-layout="list-detail"' in results
    assert 'data-compatibility-catalog="bounded-scroll"' in results
    assert 'max-h-[33rem] overflow-y-auto' in results
    assert 'max-h-[24rem]' not in results
    assert 'border-kaori-primary bg-kaori-soft/30' in results
    assert 'border-transparent bg-surface-card hover:bg-surface-hover' in results
    assert 'lg:grid-cols-12' in results
    assert 'lg:col-span-4' in results
    assert 'lg:col-span-8' in results
    assert 'bg-kaori-soft/20' not in results
    assert 'bg-kaori-soft/25' not in results
    assert 'Qualification supports compatibility; live provider validation remains authoritative.' not in results
    assert 'Qualification is not proof of live provider readiness.' in results
    assert '<ol class="mt-3 divide-y divide-outline-subtle border-t border-outline-subtle"' in results
    assert 'compatibility_registry.profile_pages > 1' in results
    assert "'Page ' ~ compatibility_registry.profile_page" in results
    assert 'profile.version_constraint' in results
    assert 'profile.upstream_lifecycle' in results
    assert 'role="region"' in results
    assert 'tabindex="0"' in results
    assert 'aria-label="Scrollable integration catalog"' in results
    assert 'data-compatibility-product-list="page-5"' in results
    assert "compatibility_registry['items']" in results
    assert 'compatibility_registry.items' not in results
    assert 'aria-current="true"' in results
    assert 'No matching integrations' in results
    assert 'Integration registry pages' in results
    assert 'hx-target="#compatibility-registry-results"' in results
    assert 'hx-target="#compatibility-registry"' not in results
    assert 'data-compatibility-product-detail="selected-only"' in results
    assert 'data-compatibility-detail-overview="primary"' in results
    assert 'data-compatibility-support-boundary="separate"' in results
    assert 'data-compatibility-qualification="paginated"' in results
    assert 'Version Qualification' in results
    assert 'General Contract' in results
    assert 'Qualified Versions' in results
    assert 'Upstream Lifecycle' in results
    assert 'KAORI Support' in results
    assert 'Readiness Authority' in results
    assert 'Live readiness authority' in results
    assert 'selected.version_scheme' in results
    assert 'selected.capability_summary' in results
    assert 'selected.qualified_versions' in results
    assert 'selected.recommended_label' in results
    assert 'selected.policy_version' in results
    assert 'selected.policy_window' in results
    assert 'selected.contract_profile' in results
    assert 'selected.upstream_lifecycle' in results
    assert 'selected.support_label' in results
    assert 'selected.support_tone' in results
    assert 'selected.validation_basis' in results
    assert 'compatibility_registry.profile_total' in results
    assert 'compatibility_registry.profiles' in results
    assert 'profile.version_constraint' in results
    assert 'profile.support_level' in results
    assert 'profile.contract_profile' in results
    assert 'compatibility_profile_page' in results
    assert 'compatibility_page' in results

    assert 'PAGE_SIZE = 5' in projection
    assert "SUPPORT_FILTERS = frozenset({'all', 'includes-current', 'extended-only'})" in projection
    assert "'profiles': qualifications[profile_offset : profile_offset + PAGE_SIZE]" in projection
    assert "'items': listed" in projection
    assert 'build_compatibility_registry(' in routes
    assert "user.has_permission('system.view')" in routes
    assert "request.headers.get('HX-Target') == 'compatibility-registry-results'" in routes
    assert "render_template('settings/general/partials/_compatibility_registry_results.html', **context)" in routes
    assert "request.headers.get('HX-Target') == 'compatibility-registry'" in routes
    assert "render_template('settings/general/partials/_compatibility_registry.html', **context)" in routes
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
    assert 'window.showOperationalToast?.(toast)' in runtime
    assert 'if (messageNode) messageNode.textContent = message' in runtime
    assert "'Browser timezone unavailable'" in runtime
    assert 'if (!timezone)' in runtime
    assert 'const unchanged = timezone === previousTimezone' in runtime
    assert 'No preference was saved.' in runtime
    assert "detectButton?.addEventListener('click', () => {" in runtime
    assert '        detect()\n        syncMode()' in runtime
    assert 'fetch(' not in runtime
    assert 'kaori:notifications-changed' not in runtime
    assert 'Activity Audit' not in runtime
    assert 'Detect Again' in settings_docs


def test_uat_general_copy_is_concise_without_truncating_provider_contracts() -> None:
    timezone = read('app/templates/settings/general/partials/_time_locale.html')
    system = read('app/templates/settings/general/partials/_system_information.html')
    definition = read('app/definitions/catalogs/integrations/compatibility.yaml')
    catalog = read('app/settings/system_information.py')
    for phrase in (
        'KAORI workspaces and reports display timestamps in your selected timezone.',
        'UTC records and explicit job/report scheduling timezones stay unchanged.',
        'Kubernetes, monitoring, databases, and provider settings stay unchanged.',
    ):
        assert phrase in timezone
        assert len(phrase) <= 80
    assert 'Secrets, credentials, database/Redis URLs, and internal endpoints.' in system
    for phrase in (
        'Kubernetes, metrics, alerts and MinIO have clear ownership.',
        'Shared evidence for jobs, delivery, and analytics.',
        'Release tracing, identity, runtime safety and testing.',
    ):
        assert phrase in catalog
        assert len(phrase) <= 80
    assert 'older qualified lines: KAORI Extended' in definition
    assert 'Current: v0.42.x' in definition
    assert 'Current: v0.34.x' in definition
    assert 'Community archived; qualified release evidence retained.' in catalog
    assert 'S3 reachability, bucket discovery, and optional object-storage governance.' in catalog
    assert 'S3 API reachability, bucket discovery, and optional object-storage governance capabilities.' not in catalog
    assert len('S3 reachability, bucket discovery, and optional object-storage governance.') <= 76
    assert 'Live S3 checks decide readiness; unqualified MinIO releases degrade, not block by version alone.' in catalog
    # Phone layouts must wrap naturally, never hide any evidence.
    assert 'truncate' not in timezone
    assert 'text-ellipsis' not in system


def test_general_titles_use_canonical_shared_guide_and_compact_capability_copy() -> None:
    # Title-level help must follow the approved Info Tip Guide, not custom tooltips.
    headings = (
        ('_time_locale.html', 'Time Zone', 'general-timezone-title-guide'),
        ('_regional_format.html', 'Regional Format', 'general-regional-title-guide'),
        ('_system_information.html', 'System Information', 'general-system-title-guide'),
        ('_compatibility_versions.html', 'Integration Compatibility', 'general-compatibility-title-guide'),
    )
    for filename, title, tip_id in headings:
        template = read(f'app/templates/settings/general/partials/{filename}')
        assert '{% import "components/info_tip.html" as info_tip %}' in template
        assert f'>{title}</h2>' in template
        assert f"'{tip_id}'" in template
        assert "variant='guide'" in template
        assert 'flex flex-wrap items-center gap-2' in template
        assert template.index(f'>{title}</h2>') < template.index(f"'{tip_id}'")
        assert template.count(f"'{tip_id}'") == 1

    catalog = read('app/settings/system_information.py')
    concise_copy = (
        'Shared evidence for jobs, delivery, and analytics.',
        'TLS inventory, governance, bulk rotation, and worker sync.',
        'Compact analytics tabs preserve canonical navigation.',
    )
    for phrase in concise_copy:
        assert phrase in catalog
        assert len(phrase) <= 62
    for obsolete in (
        'TLS certificate inventory, governance, bulk rotation, and worker-based automatic synchronization',
        'Internal content tabs that keep analytics pages compact without removing canonical navigation',
    ):
        assert obsolete not in catalog


def test_uat_compatibility_policy_columns_share_four_balanced_rows() -> None:
    template = read('app/templates/settings/general/partials/_compatibility_versions.html')
    assert 'data-compatibility-policy-reference="disclosure"' in template
    assert 'data-compatibility-policy-layout="structured-reference"' in template
    assert template.count('lg:grid lg:grid-rows-4') == 2
    assert template.count('lg:min-h-20') == 5
    assert 'data-compatibility-policy-guide="numbered"' in template
    assert '<ol class=' in template and '<dl class=' in template
    assert 'Contracts change only for breaking API behavior.' in template
    assert 'Provider APIs, RBAC, metrics and bindings determine readiness.' in template
    assert 'Contracts advance for breaking API or capability changes.' in template
    assert 'Before the window: End of Life; future: Unverified.' in template
    assert 'EOL, missing capabilities, invalid identity or failed checks block.' in template
    assert 'truncate' not in template and 'whitespace-nowrap' not in template
