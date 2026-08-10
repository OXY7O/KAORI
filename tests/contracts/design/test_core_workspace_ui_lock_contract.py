from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_provider_details_use_shared_framed_tabs():
    for relative in (
        'app/templates/integrations/kubernetes/detail.html',
        'app/templates/prometheus/instance_detail.html',
        'app/templates/alertmanager/instance_detail.html',
    ):
        source = read(relative)
        assert 'components/framed_workspace_tabs.html' in source
        assert 'framed_workspace_tabs.render(' in source
        assert 'role="tablist"' not in source


def test_dynamic_progress_uses_shared_component_in_reviewed_integration_surfaces():
    for relative in (
        'app/templates/integrations/overview.html',
        'app/templates/integrations/kubernetes/partials/_capability_workspace.html',
        'app/templates/prometheus/partials/_detail_validation_content.html',
        'app/templates/alertmanager/partials/_detail_validation_content.html',
    ):
        source = read(relative)
        assert 'components/progress_bar.html' in source
        assert 'style="width:' not in source


def test_minimum_validation_rbac_excludes_cluster_wide_secrets():
    source = read('app/templates/integrations/kubernetes/partials/_minimum_validation_rbac.html')
    baseline = source.split('kind: ClusterRoleBinding', 1)[0]
    assert '"secrets"' not in baseline


def test_operational_toast_timer_is_script_owned():
    source = read('app/templates/components/operational_toast.html')
    script = read('app/static/js/operational_toasts.js')
    assert 'data-operational-toast-timer' in source
    assert 'style=' not in source
    assert 'timerBar.animate' in script
    assert 'scaleX(0)' in script


def test_lock_verifier_is_a_static_quality_gate():
    gate = read('scripts/quality_gate.sh')
    standard = read('docs/design/KAORI_CORE_WORKSPACE_LOCK_V1.md')
    assert 'verify_core_workspace_ui_lock.py' in gate
    assert 'Status: Locked baseline' in standard
