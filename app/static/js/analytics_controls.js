(() => {
    const clampPercent = (value) => Math.max(0, Math.min(Number(value) || 0, 100));

    function analyticsTabStorageKey() {
        return `kaori:analytics-tab:${window.location.pathname}`;
    }

    function requestedAnalyticsTab(allowedTabs, defaultTab) {
        try {
            const storedTab = window.sessionStorage.getItem(analyticsTabStorageKey());
            if (allowedTabs.includes(storedTab)) return storedTab;
        } catch {
            // Storage can be unavailable in hardened browser modes.
        }

        // Preserve compatibility with bookmarked legacy hashes without using
        // hash navigation for normal tab interaction.
        const hashTab = window.location.hash.replace(/^#/, '');
        if (allowedTabs.includes(hashTab)) return hashTab;

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
                    // The in-memory Alpine state still keeps the current tab active.
                }

                // Do not write a URL hash here. Hash updates can move the viewport
                // when a matching element exists and make the workspace appear to
                // jump upward. Remove a legacy analytics-tab hash without navigation.
                const url = new URL(window.location.href);
                const currentHash = url.hash.replace(/^#/, '');
                if (tabs.includes(currentHash)) {
                    url.hash = '';
                    window.history.replaceState(window.history.state, '', url);
                }
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
        const candidate = root?.isConnected ? root : document;
        const alertsRoot = candidate?.id === 'alerts-page-content'
            ? candidate
            : candidate?.querySelector?.('#alerts-page-content') || document.querySelector('#alerts-page-content');
        if (!alertsRoot?.isConnected) return;

        window.dispatchEvent(new CustomEvent('kaori:alerts-collapse'));

        const tabset = alertsRoot.querySelector('[data-alerts-tabset]');
        if (tabset && window.Alpine && !tabset._x_dataStack) {
            window.Alpine.initTree(tabset);
        }
    }

    function stabilizeTopConsumersAfterSwap(root) {
        const candidate = root?.isConnected ? root : document;
        const pageRoot = candidate?.id === 'top-consumers-page'
            ? candidate
            : candidate?.querySelector?.('#top-consumers-page') || document.querySelector('#top-consumers-page');
        if (!pageRoot?.isConnected) return;

        const tabset = pageRoot.querySelector('[data-top-consumers-tabset]');
        if (!tabset) return;

        if (window.Alpine && !tabset._x_dataStack) {
            window.Alpine.initTree(tabset);
        }

        const activeTab = tabset._x_dataStack?.[0]?.activeTab || 'overview';
        tabset.querySelectorAll('[role="tabpanel"]').forEach((panel) => {
            const panelName = panel.id.replace('top-consumers-content-panel-', '');
            panel.hidden = panelName !== activeTab;
        });
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
    document.body.addEventListener('htmx:afterSwap', (event) => { const root = event.detail.target || document; hydrateAnalyticsUi(root); stabilizeAlertsAfterSwap(root); stabilizeTopConsumersAfterSwap(root); });
    document.body.addEventListener('htmx:afterSettle', (event) => hydrateAnalyticsUi(event.detail.elt || document));
})();
