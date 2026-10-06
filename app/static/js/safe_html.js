;(() => {
    const BLOCKED_ELEMENTS = 'script, iframe, object, embed'
    const URL_ATTRIBUTES = new Set(['href', 'src', 'xlink:href', 'action', 'formaction'])
    const JAVASCRIPT_URL = /^\s*javascript:/i

    function sanitizeParsedDocument(parsedDocument) {
        parsedDocument.querySelectorAll(BLOCKED_ELEMENTS).forEach((element) => element.remove())
        parsedDocument.querySelectorAll('*').forEach((element) => {
            for (const attribute of [...element.attributes]) {
                const name = attribute.name.toLowerCase()
                if (name.startsWith('on')) {
                    element.removeAttribute(attribute.name)
                    continue
                }
                if (URL_ATTRIBUTES.has(name) && JAVASCRIPT_URL.test(attribute.value)) {
                    element.removeAttribute(attribute.name)
                }
            }
        })
    }

    function fragment(html) {
        const parsedDocument = new DOMParser().parseFromString(String(html ?? ''), 'text/html')
        sanitizeParsedDocument(parsedDocument)

        const safeFragment = document.createDocumentFragment()
        for (const child of [...parsedDocument.body.childNodes]) {
            safeFragment.append(document.importNode(child, true))
        }
        return safeFragment
    }

    function replace(target, html) {
        if (!(target instanceof Element)) return
        target.replaceChildren(fragment(html))
    }

    window.kaoriSafeHtml = Object.freeze({ fragment, replace })
})()
