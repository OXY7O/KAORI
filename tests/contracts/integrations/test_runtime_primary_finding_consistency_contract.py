from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

SHARED_RUNTIME_TEMPLATES = (
    'app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html',
    'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html',
    'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html',
    'app/templates/integrations/registry/providers/harbor/partials/_detail_runtime.html',
)

KUBERNETES_RUNTIME = (
    'app/templates/integrations/orchestration/container_orchestrator/providers/'
    'kubernetes/partials/_runtime_workspace.html'
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_primary_finding_is_hover_free_across_current_integration_runtimes() -> None:
    decision = read('app/templates/integrations/components/_runtime_decision.html')

    assert 'Primary Finding' in decision
    assert 'components/info_tip.html' not in decision
    assert 'primary_finding_info_' not in decision
    assert 'info_tip.render(' not in decision

    for path in SHARED_RUNTIME_TEMPLATES:
        source = read(path)
        assert 'runtime_decision.render(' in source, path
        assert 'runtime_primary_finding' in source, path
        assert 'primary-finding-info' not in source, path

    kubernetes = read(KUBERNETES_RUNTIME)
    assert '{{ runtime_primary_finding }}' in kubernetes
    assert 'components/info_tip.html' not in kubernetes
    assert 'kubernetes-runtime-primary-finding-info' not in kubernetes


def test_primary_finding_uses_one_concise_state_first_grammar() -> None:
    for path in (*SHARED_RUNTIME_TEMPLATES, KUBERNETES_RUNTIME):
        source = read(path)
        assert 'runtime_identity' in source, path
        assert ' · Runtime not observed.' in source, path
        assert ' · Readiness ' in source, path
        assert ' requires attention.' in source, path
        assert ' · Healthy · Ready.' in source, path

    metrics = read(SHARED_RUNTIME_TEMPLATES[0])
    assert "runtime_product|replace('_', ' ')|title" in metrics
    assert 'runtime_primary_finding_info' not in metrics

    kubernetes = read(KUBERNETES_RUNTIME)
    assert 'lifecycle_status_label' in kubernetes
    assert 'lifecycle; readiness ' in kubernetes


def test_integrations_standard_keeps_primary_finding_detail_out_of_hover_disclosure() -> None:
    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert '**Runtime Decision Primary Finding contract.**' in standard
    assert 'must not expose an Info Tip / hover disclosure' in standard
    assert 'Detailed lifecycle, compatibility, capability, diagnostic, and remediation evidence stays in Runtime Evidence and Recent Runtime Observations.' in standard
