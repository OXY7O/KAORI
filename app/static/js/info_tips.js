;(() => {
    const previewSelector = '[data-kaori-info-tip-preview]'
    const rootSelector = '[data-kaori-info-tip]'
    const triggerSelector = '[data-kaori-info-tip-trigger]'
    const viewportMargin = 12
    const triggerGap = 8
    let active = null

    const canHover = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches

    const restorePreview = (state) => {
        if (!state?.preview || !state?.root || !state?.trigger) return

        state.preview.classList.add('hidden')
        state.preview.setAttribute('aria-hidden', 'true')
        state.preview.style.removeProperty('left')
        state.preview.style.removeProperty('top')
        state.preview.style.removeProperty('visibility')
        state.trigger.setAttribute('aria-expanded', 'false')

        if (state.nextSibling && state.nextSibling.parentNode === state.root) {
            state.root.insertBefore(state.preview, state.nextSibling)
        } else {
            state.root.appendChild(state.preview)
        }
    }

    const hideActive = () => {
        if (!active) return
        restorePreview(active)
        active = null
    }

    const positionPreview = (state) => {
        const { root, trigger, preview } = state
        const triggerRect = trigger.getBoundingClientRect()
        const previewRect = preview.getBoundingClientRect()
        const placement = root.dataset.kaoriInfoTipPlacement || 'left'

        let left =
            placement === 'right'
                ? triggerRect.left
                : triggerRect.right - previewRect.width
        left = Math.min(
            Math.max(left, viewportMargin),
            Math.max(viewportMargin, window.innerWidth - previewRect.width - viewportMargin)
        )

        let top = triggerRect.bottom + triggerGap
        if (top + previewRect.height > window.innerHeight - viewportMargin) {
            top = triggerRect.top - triggerGap - previewRect.height
        }
        top = Math.min(
            Math.max(top, viewportMargin),
            Math.max(viewportMargin, window.innerHeight - previewRect.height - viewportMargin)
        )

        preview.style.left = `${Math.round(left)}px`
        preview.style.top = `${Math.round(top)}px`
        preview.style.visibility = 'visible'
    }

    const showPreview = (root, { pinned = false } = {}) => {
        if (!(root instanceof HTMLElement)) return

        if (active?.root === root) {
            active.pinned = active.pinned || pinned
            active.trigger.setAttribute('aria-expanded', 'true')
            return
        }

        const trigger = root.querySelector(triggerSelector)
        const preview = root.querySelector(previewSelector)
        if (!(trigger instanceof HTMLElement) || !(preview instanceof HTMLElement)) return

        hideActive()

        const state = {
            root,
            trigger,
            preview,
            nextSibling: preview.nextSibling,
            pinned,
        }

        document.body.appendChild(preview)
        preview.classList.remove('hidden')
        preview.setAttribute('aria-hidden', 'false')
        preview.style.visibility = 'hidden'
        trigger.setAttribute('aria-expanded', 'true')

        positionPreview(state)
        active = state
    }

    document.addEventListener('pointerover', (event) => {
        if (!canHover()) return
        const root = event.target.closest?.(rootSelector)
        if (!(root instanceof HTMLElement)) return
        if (event.relatedTarget instanceof Node && root.contains(event.relatedTarget)) return
        showPreview(root)
    })

    document.addEventListener('pointerout', (event) => {
        if (!active || active.pinned) return

        const related = event.relatedTarget
        const root = event.target.closest?.(rootSelector)
        if (root instanceof HTMLElement && active.root === root) {
            if (
                related instanceof Node &&
                (active.root.contains(related) || active.preview.contains(related))
            ) {
                return
            }
            hideActive()
            return
        }

        if (active.preview.contains(event.target)) {
            if (
                related instanceof Node &&
                (active.preview.contains(related) || active.root.contains(related))
            ) {
                return
            }
            hideActive()
        }
    })

    document.addEventListener('focusin', (event) => {
        const trigger = event.target.closest?.(triggerSelector)
        if (!(trigger instanceof HTMLElement)) return
        const root = trigger.closest(rootSelector)
        showPreview(root)
    })

    document.addEventListener('focusout', (event) => {
        if (!active) return
        const trigger = event.target.closest?.(triggerSelector)
        if (!(trigger instanceof HTMLElement) || trigger !== active.trigger) return

        const related = event.relatedTarget
        if (
            related instanceof Node &&
            (active.root.contains(related) || active.preview.contains(related))
        ) {
            return
        }
        hideActive()
    })

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest?.(triggerSelector)
        if (trigger instanceof HTMLElement) {
            const root = trigger.closest(rootSelector)
            if (!(root instanceof HTMLElement)) return

            if (active?.root === root && active.pinned) {
                hideActive()
            } else {
                showPreview(root, { pinned: true })
            }
            return
        }

        if (
            active?.pinned &&
            event.target instanceof Node &&
            !active.root.contains(event.target) &&
            !active.preview.contains(event.target)
        ) {
            hideActive()
        }
    })

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') hideActive()
    })

    document.addEventListener('htmx:beforeSwap', hideActive)
    window.addEventListener('resize', hideActive)
    window.addEventListener('scroll', hideActive, true)
})()
