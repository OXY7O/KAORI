(() => {
    const clampPercent = (value) => Math.max(0, Math.min(Number(value) || 0, 100));

    const ANALYTICS_TAB_ACTIVE_CLASSES = [
        'border-kaori-primary',
        'bg-kaori-soft',
        'text-kaori-primary',
    ];
    const ANALYTICS_TAB_INACTIVE_CLASSES = [
        'border-transparent',
        'bg-surface-card',
        'text-content-secondary',
        'hover:border-outline-default',
        'hover:bg-surface-card',
        'hover:text-content-primary',
    ];

    function analyticsTabStorageKey(tabsetId = 'default') {
        return `kaori:analytics-tab:${window.location.pathname}:${tabsetId}`;
    }

    function requestedAnalyticsTab(allowedTabs, defaultTab, tabsetId = 'default') {
        try {
            const storedTab = window.sessionStorage.getItem(analyticsTabStorageKey(tabsetId));
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

    function clearLegacyAnalyticsHash(allowedTabs) {
        // Hash updates can move the viewport. Only remove a legacy analytics hash;
        // normal tab interaction stays in session storage and local DOM state.
        const url = new URL(window.location.href);
        const currentHash = url.hash.replace(/^#/, '');
        if (!allowedTabs.includes(currentHash)) return;

        url.hash = '';
        window.history.replaceState(window.history.state, '', url);
    }

    function analyticsTabButtons(tabset) {
        return Array.from(tabset.querySelectorAll('[data-analytics-tab-button]'));
    }

    function analyticsTabPanels(tabset) {
        return Array.from(tabset.querySelectorAll('[data-analytics-tab-panel]'));
    }

    function setAnalyticsTab(tabset, tabId, { persist = true, focus = false } = {}) {
        if (!tabset?.isConnected || !tabId) return false;

        const buttons = analyticsTabButtons(tabset);
        const allowedTabs = buttons.map((button) => button.dataset.analyticsTabButton).filter(Boolean);
        if (!allowedTabs.includes(tabId)) return false;

        const alpineState = tabset._x_dataStack?.[0];
        if (alpineState && alpineState.activeTab !== tabId) {
            alpineState.activeTab = tabId;
        }

        buttons.forEach((button) => {
            const selected = button.dataset.analyticsTabButton === tabId;
            button.setAttribute('aria-selected', selected ? 'true' : 'false');
            button.tabIndex = selected ? 0 : -1;
            button.classList.remove(...ANALYTICS_TAB_ACTIVE_CLASSES, ...ANALYTICS_TAB_INACTIVE_CLASSES);
            button.classList.add(...(selected ? ANALYTICS_TAB_ACTIVE_CLASSES : ANALYTICS_TAB_INACTIVE_CLASSES));
            if (selected && focus) button.focus({ preventScroll: true });
        });

        analyticsTabPanels(tabset).forEach((panel) => {
            panel.hidden = panel.dataset.analyticsTabPanel !== tabId;
        });

        const tabsetId = tabset.dataset.analyticsTabsetId || tabset.id || 'default';
        if (persist) {
            try {
                window.sessionStorage.setItem(analyticsTabStorageKey(tabsetId), tabId);
            } catch {
                // Native DOM state still keeps the current tab active.
            }
        }

        clearLegacyAnalyticsHash(allowedTabs);
        window.dispatchEvent(new Event('resize'));
        if (window.renderKaoriIcons) window.renderKaoriIcons();
        return true;
    }

    window.kaoriAnalyticsTabs = (defaultTab, allowedTabs, tabsetId = 'default') => {
        const tabs = Array.isArray(allowedTabs) ? allowedTabs : [];

        return {
            activeTab: requestedAnalyticsTab(tabs, defaultTab, tabsetId),
            setTab(tab) {
                if (!tabs.includes(tab)) return;
                this.activeTab = tab;
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

    function stabilizeAnalyticsTabsets(root) {
        const candidate = root?.isConnected ? root : document;
        const tabsets = [];

        if (candidate?.matches?.('[data-analytics-tabset]')) {
            tabsets.push(candidate);
        }
        candidate?.querySelectorAll?.('[data-analytics-tabset]').forEach((tabset) => tabsets.push(tabset));

        tabsets.forEach((tabset) => {
            if (!tabset?.isConnected) return;

            if (window.Alpine && !tabset._x_dataStack) {
                window.Alpine.initTree(tabset);
            }

            const buttons = analyticsTabButtons(tabset);
            const allowedTabs = buttons.map((button) => button.dataset.analyticsTabButton).filter(Boolean);
            const tabsetId = tabset.dataset.analyticsTabsetId || tabset.id || 'default';
            const alpineTab = tabset._x_dataStack?.[0]?.activeTab;
            const activeTab = allowedTabs.includes(alpineTab)
                ? alpineTab
                : requestedAnalyticsTab(allowedTabs, tabset.dataset.defaultTab, tabsetId);

            setAnalyticsTab(tabset, activeTab, { persist: false });
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

    document.addEventListener('click', (event) => {
        const button = event.target.closest?.('[data-analytics-tab-button]');
        if (!button) return;

        const tabset = button.closest('[data-analytics-tabset]');
        if (!tabset) return;

        event.preventDefault();
        setAnalyticsTab(tabset, button.dataset.analyticsTabButton);
    }, true);

    document.addEventListener('keydown', (event) => {
        const button = event.target.closest?.('[data-analytics-tab-button]');
        if (!button || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;

        const tabset = button.closest('[data-analytics-tabset]');
        if (!tabset) return;

        const buttons = analyticsTabButtons(tabset);
        const currentIndex = buttons.indexOf(button);
        if (currentIndex < 0) return;

        event.preventDefault();
        let nextIndex = currentIndex;
        if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % buttons.length;
        if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = buttons.length - 1;

        const nextButton = buttons[nextIndex];
        setAnalyticsTab(tabset, nextButton.dataset.analyticsTabButton, { focus: true });
    }, true);

    document.addEventListener('DOMContentLoaded', () => { hydrateAnalyticsUi(); stabilizeAnalyticsTabsets(document); });
    document.body.addEventListener('htmx:load', (event) => hydrateAnalyticsUi(event.detail.elt || document));
    document.body.addEventListener('htmx:afterSwap', (event) => { const root = event.detail.target || document; hydrateAnalyticsUi(root); stabilizeAlertsAfterSwap(root); stabilizeTopConsumersAfterSwap(root); stabilizeAnalyticsTabsets(root); });
    document.body.addEventListener('htmx:afterSettle', (event) => hydrateAnalyticsUi(event.detail.elt || document));
})();
