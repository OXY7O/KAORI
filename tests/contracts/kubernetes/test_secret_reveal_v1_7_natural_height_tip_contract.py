from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_global_gate_guidance_uses_compact_activation_tip() -> None:
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')

    assert 'Activation Tip' in page
    assert 'Policy-enabled Namespace configuration is ready, but target selection is locked by the global kill switch.' in page
    assert 'KUBERNETES_SECRET_REVEAL_ENABLED=true' in page
    assert 'restart KAORI' in page
    assert '<span class="mt-1.5 block text-xs leading-5 text-status-warning-text">' not in page


def test_protected_reveal_returns_to_natural_context_rail_height() -> None:
    context_rail = read('app/templates/components/context_rail.html')
    page = read('app/templates/kubernetes_operations/secrets/reveal.html')

    assert "layout_classes(width='default')" in context_rail
    assert 'xl:items-start' in context_rail
    assert 'rail_classes()' in context_rail
    assert 'items-stretch' not in context_rail
    assert "align='start'" not in context_rail
    assert 'rail_classes(fill=false)' not in context_rail

    assert "context_rail.layout_classes('wide')" in page
    assert 'context_rail.rail_classes()' in page
    assert "context_rail.layout_classes('wide', 'stretch')" not in page
    assert 'context_rail.rail_classes(true)' not in page
    assert "extra_classes='h-full'" not in page


def test_administration_readiness_and_boundary_cards_use_content_height() -> None:
    page = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    assert 'grid gap-4 p-5 sm:p-6 xl:grid-cols-12' in page
    assert 'grid items-stretch gap-4' not in page
    assert 'h-full overflow-hidden rounded-2xl' not in page
    assert 'flex h-full flex-col overflow-hidden rounded-2xl' not in page
    assert 'grid flex-1 gap-3' not in page
    assert 'grid gap-3 p-4 sm:grid-cols-2 sm:p-5' in page


def test_secret_reveal_v17_keeps_neutral_dark_mode_surfaces() -> None:
    protected = read('app/templates/kubernetes_operations/secrets/reveal.html')
    administration = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')

    for source in (protected, administration):
        assert 'bg-white' not in source
    assert 'bg-surface-card' in protected
    assert 'bg-surface-card' in administration
