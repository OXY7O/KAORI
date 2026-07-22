from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_kubernetes_registry_uses_canonical_connection_registry_header():
    source = (
        ROOT
        / 'app/templates/integrations/kubernetes/partials/_registry.html'
    ).read_text(encoding='utf-8')

    assert 'rounded-2xl border border-outline-default' in source
    assert 'text-lg font-semibold text-content-primary' in source
    assert 'mt-1 text-sm leading-6 text-content-secondary' in source
    assert 'rounded-xl bg-kaori-soft text-kaori-primary' in source
    assert 'htmx-indicator mt-4 h-1' in source
    assert '{{ pagination.total_items }} registered' not in source


def test_kubernetes_empty_state_matches_connection_registry_pattern():
    source = (
        ROOT
        / 'app/templates/integrations/kubernetes/partials/_registry.html'
    ).read_text(encoding='utf-8')

    assert "empty_state_label = 'Setup Required'" in source
    assert "empty_state_title = 'No Kubernetes Connections Found'" in source
    assert (
        "empty_state_description = 'Register a Kubernetes API connection "
        "or adjust the active filters.'"
    ) in source
    assert "empty_state_action_label = 'Register Connection'" in source
    assert "empty_state_min_height = 'min-h-[190px]'" in source
