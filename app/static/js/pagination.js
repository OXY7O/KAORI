(() => {
    const PAGE_PARAM = 'page';

    function pageWindow(current, total) {
        if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1);
        if (current <= 3) return [1, 2, 3, 4, 'ellipsis', total];
        if (current >= total - 2) return [1, 'ellipsis', total - 3, total - 2, total - 1, total];
        return [1, 'ellipsis', current - 1, current, current + 1, 'ellipsis', total];
    }

    function replacePage(urlValue, page) {
        if (!urlValue) return '';
        try {
            const url = new URL(urlValue, window.location.origin);
            url.searchParams.set(PAGE_PARAM, String(page));
            return `${url.pathname}${url.search}${url.hash}`;
        } catch (_) {
            return urlValue.replace(/([?&]page=)[^&]*/i, `$1${page}`);
        }
    }

    function sourceControl(container) {
        const group = container.parentElement;
        if (!group) return null;
        return group.querySelector('a[hx-get], button[hx-get], a[href]');
    }

    function buildPageLink(source, page, current) {
        if (page === current) {
            const span = document.createElement('span');
            span.className = 'inline-flex min-h-9 min-w-9 items-center justify-center rounded-md border border-kaori-primary/30 bg-kaori-soft px-3 py-2 text-xs font-semibold text-kaori-primary';
            span.setAttribute('aria-current', 'page');
            span.textContent = String(page);
            return span;
        }

        const link = document.createElement('a');
        link.className = 'inline-flex min-h-9 min-w-9 cursor-pointer items-center justify-center rounded-md border border-outline-default bg-surface-card px-3 py-2 text-xs font-semibold text-content-secondary transition-colors duration-150 hover:border-kaori-primary/40 hover:bg-kaori-soft hover:text-kaori-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-kaori-accent/60';
        link.textContent = String(page);
        link.setAttribute('aria-label', `Go to page ${page}`);

        if (source) {
            for (const attr of ['hx-target', 'hx-swap', 'hx-indicator', 'hx-push-url', 'hx-include', 'hx-sync', 'hx-on::before-request']) {
                if (source.hasAttribute(attr)) link.setAttribute(attr, source.getAttribute(attr));
            }
            const href = source.getAttribute('href');
            const hxGet = source.getAttribute('hx-get');
            if (href) link.setAttribute('href', replacePage(href, page));
            if (hxGet) link.setAttribute('hx-get', replacePage(hxGet, page));
            if (!href && hxGet) link.setAttribute('href', replacePage(hxGet, page));
        }
        return link;
    }

    function render(container) {
        const current = Number(container.dataset.currentPage || 1);
        const total = Math.max(1, Number(container.dataset.totalPages || 1));
        const source = sourceControl(container);
        container.replaceChildren();

        for (const item of pageWindow(current, total)) {
            if (item === 'ellipsis') {
                const ellipsis = document.createElement('span');
                ellipsis.className = 'inline-flex min-h-9 min-w-6 items-center justify-center text-xs font-semibold text-content-muted';
                ellipsis.textContent = '…';
                ellipsis.setAttribute('aria-hidden', 'true');
                container.appendChild(ellipsis);
            } else {
                container.appendChild(buildPageLink(source, item, current));
            }
        }
    }

    function paginationContainers(root = document) {
        const containers = [];
        if (root instanceof Element && root.matches('[data-kaori-numeric-pagination]')) {
            containers.push(root);
        }
        if (typeof root.querySelectorAll === 'function') {
            containers.push(...root.querySelectorAll('[data-kaori-numeric-pagination]'));
        }
        return containers;
    }

    function renderAll(root = document) {
        paginationContainers(root).forEach(render);
        if (window.htmx) window.htmx.process(root);
    }

    function renderAfterHtmxSwap(event) {
        const target = event?.detail?.target;
        window.requestAnimationFrame(() => {
            if (target && target.isConnected) {
                renderAll(target);
            } else {
                renderAll(document);
            }
        });
    }

    document.addEventListener('change', (event) => {
        const control = event.target.closest('[data-kaori-auto-submit]');
        if (!control || !control.form) return;
        control.form.requestSubmit();
    });

    document.addEventListener('DOMContentLoaded', () => renderAll(document));
    document.addEventListener('htmx:afterSwap', renderAfterHtmxSwap);
    document.addEventListener('htmx:afterSettle', renderAfterHtmxSwap);
})();
