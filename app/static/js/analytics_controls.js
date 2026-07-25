(() => {
    window.kaoriAnalyticsTabs = (defaultTab, allowedTabs) => {
        const tabs = Array.isArray(allowedTabs) ? allowedTabs : [];
        const requestedTab = window.location.hash.replace(/^#/, '');
        const initialTab = tabs.includes(requestedTab) ? requestedTab : defaultTab;

        return {
            activeTab: initialTab,
            setTab(tab) {
                if (!tabs.includes(tab)) return;

                this.activeTab = tab;

                const url = new URL(window.location.href);
                url.hash = tab;
                window.history.replaceState(null, '', url);
            },
        };
    };

    function resetDependentFields(control) {
        const form = control.form;
        const specification = control.dataset.kaoriResetFields;

        if (!form || !specification) return;

        for (const entry of specification.split(',')) {
            const [rawName, ...rawValue] = entry.split('=');
            const name = rawName.trim();
            if (!name) continue;

            const field = form.elements.namedItem(name);
            if (!field || field instanceof RadioNodeList) continue;

            field.value = rawValue.join('=').trim();
        }
    }

    document.addEventListener(
        'change',
        (event) => {
            const control = event.target.closest('[data-kaori-reset-fields]');
            if (control) resetDependentFields(control);
        },
        true,
    );
})();
