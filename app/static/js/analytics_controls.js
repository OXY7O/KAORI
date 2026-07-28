(() => {
    const clampPercent = (value) => Math.max(0, Math.min(Number(value) || 0, 100));

    function analyticsTabStorageKey() {
        return `kaori:analytics-tab:${window.location.pathname}`;
    }

    function requestedAnalyticsTab(allowedTabs, defaultTab) {
        const hashTab = window.location.hash.replace(/^#/, '');
        if (allowedTabs.includes(hashTab)) return hashTab;

        try {
            const storedTab = window.sessionStorage.getItem(analyticsTabStorageKey());
            if (allowedTabs.includes(storedTab)) return storedTab;
        } catch {
            // Storage can be unavailable in hardened browser modes.
        }

        return defaultTab;
    }

    window.kaoriAnalyticsTabs = (defaultTab, allowedTabs) => {
        const tabs = Array.isArray(allowedTabs) ? allowedTabs : [];

        return {
            activeTab: requestedAnalyticsTab(tabs, defaultTab),
            setTab(tab) {
                if (!tabs.includes(tab)) return;

                this.activeTab = tab;

                try {
                    window.sessionStorage.setItem(analyticsTabStorageKey(), tab);
                } catch {
                    // The URL hash remains the fallback persistence mechanism.
                }

                const url = new URL(window.location.href);
                url.hash = tab;
                window.history.replaceState(null, '', url);
            },
        };
    };

    function hydrateProgressBars(root = document) {
        root.querySelectorAll('.kaori-progress-fill[data-progress]').forEach((element) => {
            element.style.width = `${clampPercent(element.dataset.progress)}%`;
        });
    }

    function hydrateProgressRings(root = document) {
        root.querySelectorAll('[data-progress-ring]').forEach((element) => {
            const value = clampPercent(element.dataset.progressRing);
            element.setAttribute('stroke-dasharray', `${value} 100`);
        });
    }

    function resetDependentFields(control) {
        const form = control.form;
        const specification = control.dataset.kaoriResetFields;

        if (!form || !specification) return;

        for (const entry of specification.split(',')) {
            const [rawName, ...rawValue] = entry.split('=');
            const name = rawName.trim();
            if (!name) continue;

            const field = form.elements.namedItem(name);
            if (!field || (typeof RadioNodeList !== 'undefined' && field instanceof RadioNodeList)) continue;

            field.value = rawValue.join('=').trim();
        }
    }


    function stabilizeAlertsAfterSwap(root) {
        const alertsRoot = root?.id === 'alerts-page-content'
            ? root
            : root?.querySelector?.('#alerts-page-content');
        if (!alertsRoot) return;

        window.dispatchEvent(new CustomEvent('kaori:alerts-collapse'));

        const tabset = alertsRoot.querySelector('[data-alerts-tabset]');
        if (tabset && window.Alpine && !tabset._x_dataStack) {
            window.Alpine.initTree(tabset);
        }
    }

    function hydrateAnalyticsUi(root = document) {
        hydrateProgressBars(root);
        hydrateProgressRings(root);

        if (window.renderKaoriIcons) {
            window.renderKaoriIcons();
        } else if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    document.addEventListener('change', (event) => {
        const control = event.target.closest('[data-kaori-reset-fields]');
        if (control) resetDependentFields(control);
    }, true);

    document.addEventListener('DOMContentLoaded', () => hydrateAnalyticsUi());
    document.body.addEventListener('htmx:load', (event) => hydrateAnalyticsUi(event.detail.elt || document));
    document.body.addEventListener('htmx:afterSwap', (event) => { const root = event.detail.target || document; hydrateAnalyticsUi(root); stabilizeAlertsAfterSwap(root); });
    document.body.addEventListener('htmx:afterSettle', (event) => hydrateAnalyticsUi(event.detail.elt || document));
})();
