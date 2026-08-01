from pathlib import Path


def test_secret_choice_card_selected_state_has_no_double_ring():
    styles = Path('frontend/styles.css').read_text()
    assert '.secret-type-choice:has(.secret-type-input:focus-visible)' in styles
    assert '.secret-type-option::before' in styles
    assert 'box-shadow: none;' in styles
    assert '0 0 0 2px var(--kaori-brand-primary)' not in styles
    assert 'inset 0 0 0 1px var(--kaori-brand-border)' not in styles


def test_selected_indicator_uses_soft_badge_without_extra_border():
    template = Path('app/templates/components/choice_card_group.html').read_text()
    marker = 'secret-type-selected-indicator inline-flex'
    selected = template[template.index(marker): template.index(marker) + 260]
    assert 'bg-kaori-soft' in selected
    assert 'border border-brand-outline' not in selected
