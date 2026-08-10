from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_shared_operation_actions_use_high_contrast_hover_in_both_modes() -> None:
    action_button = read('app/templates/components/action_button.html')
    operation_ui = read('app/templates/components/kubernetes_operation_ui.html')
    view_more = read('app/templates/components/view_more_content.html')

    assert 'hover:bg-kaori-primary hover:text-white' in action_button
    assert 'active:bg-kaori-primary-dark active:text-white' in action_button
    assert 'dark:text-kaori-accent' in operation_ui
    assert 'hover:bg-kaori-primary hover:text-white' in operation_ui
    assert 'hover:bg-surface-selected' in view_more


def test_hero_context_badges_and_actions_remain_readable_on_violet_surface() -> None:
    hero = read('app/templates/components/page_hero.html')

    assert 'bg-white/95' in hero
    styles = read('frontend/styles.css')
    assert 'kaori-hero-status-badge' in hero
    assert '.kaori-hero-status-info' in styles
    assert '<span class="truncate">{{ label }}</span>' not in hero
    assert 'text-kaori-primary-dark' in hero
    assert 'hover:bg-white/90' in hero


def test_secret_type_selection_uses_one_native_checked_authority() -> None:
    choice = read('app/templates/components/choice_card_group.html')
    styles = read('frontend/styles.css')

    assert 'secret-type-input sr-only' in choice
    assert 'x-show=' not in choice
    assert "data-selected='true'" not in styles
    assert '.secret-type-input:checked + .secret-type-option' in styles
    assert 'secret-type-selected-indicator' in styles


def test_delete_action_oob_fragments_only_render_for_htmx_responses() -> None:
    for relative in (
        'app/templates/kubernetes_operations/secrets/_delete_operation_result.html',
        'app/templates/kubernetes_operations/configmaps/_operation_response.html',
    ):
        source = read(relative)
        assert 'operation_feedback_oob.html' in source
        assert 'hx-swap-oob="outerHTML"' not in source or 'include' in source
