from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_info_tip_uses_one_non_modal_popover_for_all_input_methods() -> None:
    component = read('app/templates/components/info_tip.html')
    script = read('app/static/js/info_tips.js')
    standard = read('docs/design/components/INFO_TIP.md')

    assert 'data-kaori-info-tip-trigger' in component
    assert 'aria-expanded="false"' in component
    assert 'aria-controls="{{ id }}-tooltip"' in component
    assert 'aria-describedby="{{ id }}-tooltip"' in component
    assert 'role="tooltip"' in component
    assert 'aria-hidden="true"' in component

    assert '<dialog' not in component
    assert 'data-kaori-dialog-open' not in component
    assert 'data-dialog-target' not in component
    assert 'aria-haspopup="dialog"' not in component
    assert 'data-kaori-native-dialog' not in component

    for token in (
        "document.body.appendChild(preview)",
        "document.addEventListener('pointerover'",
        "document.addEventListener('focusin'",
        "document.addEventListener('click'",
        "event.key === 'Escape'",
        "active.preview.contains(event.target)",
        "trigger.setAttribute('aria-expanded', 'true')",
        "preview.setAttribute('aria-hidden', 'false')",
    ):
        assert token in script

    assert 'one non-modal anchored popover' in standard
    assert 'immediately beside the section title' in standard
    assert 'native dialog' not in standard.lower()


def test_info_tip_viewport_controller_prevents_ordinary_overflow_clipping() -> None:
    component = read('app/templates/components/info_tip.html')
    script = read('app/static/js/info_tips.js')

    assert 'fixed z-[120]' in component
    assert 'max-w-[calc(100vw-2rem)]' in component
    assert 'max-h-[calc(100dvh-2rem)]' in component
    assert 'overflow-y-auto' in component
    assert 'viewportMargin = 12' in script
    assert 'window.innerWidth - previewRect.width - viewportMargin' in script
    assert 'window.innerHeight - previewRect.height - viewportMargin' in script
