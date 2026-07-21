from pathlib import Path

TEMPLATE_ROOT = Path('app/templates')


def _templates():
    return list(TEMPLATE_ROOT.rglob('*.html'))


def test_canonical_state_components_exist():
    assert (TEMPLATE_ROOT / 'components/states/_empty_state.html').is_file()
    assert (TEMPLATE_ROOT / 'components/states/_blocked_state.html').is_file()


def test_removed_legacy_empty_state_partial_is_not_referenced():
    legacy = 'analytics/overview/partials/_empty_state.html'
    assert not (TEMPLATE_ROOT / legacy).exists()
    offenders = [str(path) for path in _templates() if legacy in path.read_text()]
    assert offenders == []


def test_shared_state_markers_are_preserved():
    empty_component = (TEMPLATE_ROOT / 'components/states/_empty_state.html').read_text()
    blocked_component = (TEMPLATE_ROOT / 'components/states/_blocked_state.html').read_text()
    assert 'data-kaori-empty-state' in empty_component
    assert 'data-kaori-blocked-state' in blocked_component


def test_state_adapter_templates_contain_no_duplicate_visual_markup():
    adapters = [
        TEMPLATE_ROOT / 'components/dependencies/_blocker.html',
        TEMPLATE_ROOT / 'components/cluster/_onboarding_banner.html',
        TEMPLATE_ROOT / 'analytics/components/_blocked_posture.html',
    ]
    forbidden = ('<section', '<article', 'rounded-xl border', 'bg-kaori-soft px-')
    for adapter in adapters:
        source = adapter.read_text()
        assert "components/states/_blocked_state.html" in source
        for token in forbidden:
            assert token not in source, f'{adapter} duplicates canonical blocked-state markup: {token}'


def test_migrated_registry_empty_states_use_shared_component():
    templates = [
        TEMPLATE_ROOT / 'cluster/partials/_table.html',
        TEMPLATE_ROOT / 'integrations/kubernetes.html',
        TEMPLATE_ROOT / 'integrations/kubernetes/partials/_registry.html',
        TEMPLATE_ROOT / 'integrations/partials/_table.html',
        TEMPLATE_ROOT / 'settings/data_lifecycle/partials/_history.html',
    ]
    for template in templates:
        assert "components/states/_empty_state.html" in template.read_text()


def test_legacy_domain_state_partials_are_removed():
    legacy_paths = [
        TEMPLATE_ROOT / 'analytics/overview/partials/_empty_state.html',
        TEMPLATE_ROOT / 'analytics/overview/partials/_hero_posture_blocked.html',
        TEMPLATE_ROOT / 'dashboards/kubernetes/partials/_cluster_required_empty_state.html',
    ]
    for legacy in legacy_paths:
        assert not legacy.exists(), f'legacy state partial still exists: {legacy}'

    legacy_references = [
        'analytics/overview/partials/_empty_state.html',
        'analytics/overview/partials/_hero_posture_blocked.html',
        'dashboards/kubernetes/partials/_cluster_required_empty_state.html',
    ]
    for reference in legacy_references:
        offenders = [str(path) for path in _templates() if reference in path.read_text()]
        assert offenders == [], f'legacy state partial still referenced: {reference}'


def test_dashboard_cluster_prerequisites_use_canonical_blocked_state():
    templates = [
        TEMPLATE_ROOT / 'dashboards/kubernetes/partials/_top_consumers.html',
        TEMPLATE_ROOT / 'dashboards/kubernetes/partials/_forecast_risk.html',
        TEMPLATE_ROOT / 'dashboards/kubernetes/partials/_capacity_snapshot.html',
        TEMPLATE_ROOT / 'dashboards/kubernetes/partials/_alerts_summary.html',
    ]
    for template in templates:
        source = template.read_text()
        assert "components/states/_blocked_state.html" in source
        assert '_cluster_required_empty_state.html' not in source
