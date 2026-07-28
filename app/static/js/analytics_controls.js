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


    function connectedSwapRoot(event) {
        const candidates = [
            event?.target,
            event?.detail?.target,
            event?.detail?.elt,
        ];

        for (const candidate of candidates) {
            if (candidate instanceof Element && candidate.isConnected) return candidate;
        }

        return document;
    }

    function alertsSwapBoundary(root) {
        if (root instanceof Document) {
            return root.querySelector('[data-alerts-swap-boundary]');
        }
        if (!(root instanceof Element)) return null;
        if (root.matches('[data-alerts-swap-boundary]')) return root;
        return root.querySelector('[data-alerts-swap-boundary]')
            || root.closest('[data-alerts-swap-boundary]');
    }

    function initializePendingAlpineComponents(root) {
        if (!window.Alpine || !(root instanceof Element)) return;

        const components = [];
        if (root.matches('[x-data]')) components.push(root);
        components.push(...root.querySelectorAll('[x-data]'));

        if (components.some((component) => !component._x_dataStack)) {
            window.Alpine.initTree(root);
        }
    }

    function reconcileAlertsTabPanels(root) {
        const pageRoot = root.id === 'alerts-page-content'
            ? root
            : document.getElementById('alerts-page-content');
        const tabset = pageRoot?.querySelector('[data-alerts-tabset]');
        if (!tabset) return;

        const panels = [...tabset.querySelectorAll('[data-alerts-tab-panel]')];
        const allowedTabs = panels.map((panel) => panel.dataset.alertsTabPanel);
        let activeTab = requestedAnalyticsTab(allowedTabs, 'alerts');

        if (window.Alpine?.$data) {
            try {
                const alpineData = window.Alpine.$data(tabset);
                if (allowedTabs.includes(alpineData?.activeTab)) activeTab = alpineData.activeTab;
            } catch {
                // Native hidden state remains the safe fallback while Alpine settles.
            }
        }

        panels.forEach((panel) => {
            panel.hidden = panel.dataset.alertsTabPanel !== activeTab;
        });
    }

    function stabilizeAlertsAfterSwap(event) {
        const root = connectedSwapRoot(event);
        const boundary = alertsSwapBoundary(root);
        if (!boundary) return;

        initializePendingAlpineComponents(boundary);
        window.dispatchEvent(new CustomEvent('kaori:alerts-collapse'));
        reconcileAlertsTabPanels(boundary);
    }


    function collapseAlertsBeforeRequest(event) {
        const requestElement = event?.detail?.elt;
        if (!(requestElement instanceof Element)) return;
        if (!requestElement.closest('#alerts-page-content')) return;

        window.dispatchEvent(new CustomEvent('kaori:alerts-collapse'));
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
    document.body.addEventListener('htmx:beforeRequest', collapseAlertsBeforeRequest);
    document.body.addEventListener('htmx:load', (event) => hydrateAnalyticsUi(event.detail.elt || document));
    document.body.addEventListener('htmx:afterSwap', (event) => { const root = connectedSwapRoot(event); hydrateAnalyticsUi(root); stabilizeAlertsAfterSwap(event); });
    document.body.addEventListener('htmx:afterSettle', (event) => { const root = connectedSwapRoot(event); hydrateAnalyticsUi(root); stabilizeAlertsAfterSwap(event); });
})();
