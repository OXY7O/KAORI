from pathlib import Path


def test_kubernetes_runtime_distinguishes_automatic_health_from_on_demand_validation() -> None:
    tasks = Path('app/integrations/runtime/tasks.py').read_text(encoding='utf-8')
    workspace = Path('app/templates/integrations/kubernetes/partials/_runtime_workspace.html').read_text(encoding='utf-8')
    assert 'Full capability validation remains an explicit on-demand validation job.' in tasks
    assert 'Scheduled Runtime Health' in workspace
    assert 'Full Validation On Demand' in workspace
    assert 'does not rebuild API discovery or RBAC evidence' in workspace


def test_kubernetes_lifecycle_policy_and_history_show_current_and_accepted_ranges() -> None:
    compatibility = Path('app/integrations/compatibility.py').read_text(encoding='utf-8')
    adapter = Path('app/integrations/runtime/kubernetes_adapter.py').read_text(encoding='utf-8')
    history = Path('app/templates/integrations/partials/_runtime_history.html').read_text(encoding='utf-8')
    assert "KUBERNETES_CURRENT_VERSION_LABEL = 'v1.34–v1.36'" in compatibility
    assert "KUBERNETES_SUPPORTED_VERSION_CONSTRAINT = '>=1.20,<2.0'" in compatibility
    assert 'kubernetes_lifecycle_policy' in adapter
    assert "'lifecycle_policy': lifecycle_policy" in adapter
    assert 'KAORI Current Band' in history
    assert 'Accepted Compatibility Contract' in history
    assert 'Selected Stable APIs' in history
    assert 'Legacy API Fallbacks' in history
