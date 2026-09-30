;(() => {
    const previewSelector = '[data-kaori-info-tip-preview]'
    const rootSelector = '[data-kaori-info-tip]'
    const triggerSelector = '[data-kaori-info-tip-trigger]'
    const viewportMargin = 12
    const triggerGap = 8
    let active = null

    const canHover = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches

    const restorePreview = (state) => {
        if (!state?.preview || !state?.root) return
        state.preview.classList.add('hidden')
        state.preview.style.removeProperty('left')
        state.preview.style.removeProperty('top')
        state.preview.style.removeProperty('visibility')
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

    const showPreview = (root) => {
        if (!canHover() || !(root instanceof HTMLElement)) return
        const trigger = root.querySelector(triggerSelector)
        const preview = root.querySelector(previewSelector)
        if (!(trigger instanceof HTMLElement) || !(preview instanceof HTMLElement)) return

        hideActive()

        const nextSibling = preview.nextSibling
        document.body.appendChild(preview)
        preview.classList.remove('hidden')
        preview.style.visibility = 'hidden'

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
        active = { root, preview, nextSibling }
    }

    document.addEventListener('pointerover', (event) => {
        const root = event.target.closest?.(rootSelector)
        if (!(root instanceof HTMLElement)) return
        if (event.relatedTarget instanceof Node && root.contains(event.relatedTarget)) return
        showPreview(root)
    })

    document.addEventListener('pointerout', (event) => {
        const root = event.target.closest?.(rootSelector)
        if (!(root instanceof HTMLElement) || !active || active.root !== root) return
        if (event.relatedTarget instanceof Node && root.contains(event.relatedTarget)) return
        hideActive()
    })

    document.addEventListener('click', (event) => {
        if (event.target.closest?.(triggerSelector)) hideActive()
    })

    document.addEventListener('htmx:beforeSwap', hideActive)
    window.addEventListener('resize', hideActive)
    window.addEventListener('scroll', hideActive, true)
})()
