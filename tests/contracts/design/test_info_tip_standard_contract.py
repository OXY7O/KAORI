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
        'portal.appendChild(preview)',
        "document.addEventListener('pointerover'",
        "document.addEventListener('focusin'",
        "document.addEventListener('click'",
        "event.key === 'Escape'",
        'active.preview.contains(event.target)',
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


def test_guide_variant_renders_compact_label_and_reuses_existing_popover() -> None:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    macro = env.get_template('components/info_tip.html').module.render
    guide = str(
        macro(
            'example-guide',
            'Inventory Guide',
            'Review committed evidence.',
            items=['One point'],
            placement='right',
            variant='guide',
        )
    )
    icon = str(macro('example-icon', 'Field help', 'An inline explanation.'))

    assert 'data-kaori-info-tip-variant="guide"' in guide
    assert 'data-lucide="info"' in guide
    assert '<span>Guide</span>' in guide
    assert 'rounded-md border border-brand-outline' in guide
    assert 'rounded-full border border-brand-outline' not in guide
    assert 'bg-kaori-soft' in guide
    assert 'border-brand-outline' in guide and 'focus-visible:ring-2' in guide
    assert 'aria-controls="example-guide-tooltip"' in guide
    assert 'aria-expanded="false"' in guide
    assert 'role="tooltip"' in guide
    assert 'Review committed evidence.' in guide and 'One point' in guide

    assert 'data-kaori-info-tip-variant="icon"' in icon
    assert 'data-lucide="info"' in icon
    assert 'data-lucide="circle-help"' not in icon
    assert '<span>Guide</span>' not in icon
    assert 'role="tooltip"' in icon


def test_title_level_guides_share_existing_portal_controller() -> None:
    source = read('app/templates/components/info_tip.html')
    script = read('app/static/js/info_tips.js')
    doc = read('docs/design/components/INFO_TIP.md')

    assert "variant='icon'" in source
    assert "guide_variant = variant == 'guide' and not button_text" in source
    assert 'data-kaori-info-tip-preview' in source
    assert "variant='guide'" in doc
    assert 'information glyph, never a question-mark icon' in doc
    assert 'data-lucide="circle-help"' not in source
    assert 'field-level' in doc
    assert 'portal.appendChild(preview)' in script
    assert "document.addEventListener('htmx:beforeSwap'" in script


def test_shared_info_tip_geometry_and_readable_popover_contract() -> None:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    render = env.get_template('components/info_tip.html').module.render
    icon = str(
        render(
            'info-compact',
            'Tenant Registry status',
            'Committed Tenant lifecycle.',
            items=[
                'Ready — Tenant governance is active.',
                'Blocked — Tenant stays valid while an action fails closed.',
            ],
        )
    )
    guide = str(
        render(
            'info-guide',
            'Tenant Registry status',
            'Committed Tenant lifecycle.',
            items=[
                'Ready — Tenant governance is active.',
            ],
            variant='guide',
        )
    )

    assert 'w-96' in icon
    assert 'w-[26rem]' in guide

    for markup in (icon, guide):
        assert 'max-w-[calc(100vw-2rem)]' in markup
        assert 'max-h-[calc(100dvh-2rem)]' in markup
        assert 'overflow-y-auto rounded-lg border border-outline-default' in markup
        assert 'bg-surface-elevated text-left shadow-lg' in markup
        assert 'border-b border-outline-subtle bg-surface-card' in markup
        assert 'rounded-md bg-kaori-soft text-kaori-primary' in markup
        assert 'text-sm font-semibold leading-5 text-content-primary' in markup
        assert 'text-sm leading-5 text-content-secondary' in markup
        assert 'divide-y divide-outline-subtle' in markup
        assert 'min-w-0 flex-1 break-words' in markup
        assert 'Ready — Tenant governance is active.' in markup

    doc = read('docs/design/components/INFO_TIP.md')
    assert 'compact label geometry (`rounded-md`' in doc
    assert '384px for icon help and 416px for Guide help' in doc
