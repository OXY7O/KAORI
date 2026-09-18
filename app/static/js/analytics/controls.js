;(() => {
    const clampPercent = (value) => Math.max(0, Math.min(Number(value) || 0, 100))

    function analyticsTabStorageKey(tabsetId = 'default') {
        return `kaori:analytics-tab:${window.location.pathname}:${tabsetId}`
    }

    function requestedAnalyticsTab(allowedTabs, defaultTab, tabsetId = 'default') {
        const requestedTab = new URL(window.location.href).searchParams.get('tab')
        if (allowedTabs.includes(requestedTab)) return requestedTab

        try {
            const storedTab = window.sessionStorage.getItem(analyticsTabStorageKey(tabsetId))
            if (allowedTabs.includes(storedTab)) return storedTab
        } catch {
            // Storage can be unavailable in hardened browser modes.
        }

        return defaultTab
    }

    function analyticsTabButtons(tabset) {
        return Array.from(tabset.querySelectorAll('[data-analytics-tab-button]')).filter(
            (button) => button.closest('[data-analytics-tabset]') === tabset
        )
    }

    function analyticsTabPanels(tabset) {
        return Array.from(tabset.querySelectorAll('[data-analytics-tab-panel]')).filter(
            (panel) => panel.closest('[data-analytics-tabset]') === tabset
        )
    }

    function notifyAnalyticsTabVisible(panel, tabId, tabsetId) {
        if (!panel) return

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (!panel.isConnected || panel.hidden) return
                panel.dispatchEvent(
                    new CustomEvent('kaori:analytics-tab-visible', {
                        bubbles: true,
                        detail: { tabId, tabsetId },
                    })
                )
                window.dispatchEvent(new Event('resize'))
            })
        })
    }

    function tabStateClasses(button, state) {
        const value = state === 'active' ? button.dataset.kaoriTabActiveClasses : button.dataset.kaoriTabInactiveClasses
        return String(value || '')
            .trim()
            .split(/\s+/)
            .filter(Boolean)
    }

    function setAnalyticsTab(tabset, tabId, { persist = true, focus = false } = {}) {
        if (!tabset?.isConnected || !tabId) return false

        const buttons = analyticsTabButtons(tabset)
        const allowedTabs = buttons.map((button) => button.dataset.analyticsTabButton).filter(Boolean)
        if (!allowedTabs.includes(tabId)) return false

        buttons.forEach((button) => {
            const selected = button.dataset.analyticsTabButton === tabId
            button.setAttribute('aria-selected', selected ? 'true' : 'false')
            button.tabIndex = selected ? 0 : -1
            const activeClasses = tabStateClasses(button, 'active')
            const inactiveClasses = tabStateClasses(button, 'inactive')
            button.classList.remove(...activeClasses, ...inactiveClasses)
            button.classList.add(...(selected ? activeClasses : inactiveClasses))
            if (selected && focus) button.focus({ preventScroll: true })
        })

        analyticsTabPanels(tabset).forEach((panel) => {
            panel.hidden = panel.dataset.analyticsTabPanel !== tabId
        })

        if (tabset.dataset.analyticsUpdateQuery !== 'false') {
            const pageRoot = tabset.closest('[id$="-page"]') || document
            pageRoot.querySelectorAll('[data-analytics-preserve-tab] input[name="tab"]').forEach((field) => {
                field.value = tabId
            })
        }

        const tabsetId = tabset.dataset.analyticsTabsetId || tabset.id || 'default'
        if (persist && tabset.dataset.analyticsUpdateQuery !== 'false') {
            const url = new URL(window.location.href)
            url.searchParams.set('tab', tabId)
            window.history.replaceState({}, '', url)
        }

        if (persist) {
            try {
                window.sessionStorage.setItem(analyticsTabStorageKey(tabsetId), tabId)
            } catch {
                // Native DOM state still keeps the current tab active.
            }
        }

        const activePanel = analyticsTabPanels(tabset).find((panel) => panel.dataset.analyticsTabPanel === tabId)
        if (activePanel) {
            const activationTargets = [
                ...(activePanel.matches?.('[hx-trigger*="kaori:analytics-tab-activated"]') ? [activePanel] : []),
                ...activePanel.querySelectorAll('[hx-trigger*="kaori:analytics-tab-activated"]'),
            ]
            activationTargets.forEach((target) => {
                if (window.htmx?.trigger) {
                    window.htmx.trigger(target, 'kaori:analytics-tab-activated')
                } else {
                    target.dispatchEvent(new CustomEvent('kaori:analytics-tab-activated', { bubbles: true }))
                }
            })
            notifyAnalyticsTabVisible(activePanel, tabId, tabsetId)
        }
        if (window.renderKaoriIcons) window.renderKaoriIcons()
        return true
    }

    function hydrateProgressBars(root = document) {
        root.querySelectorAll('.kaori-progress-fill[data-progress]').forEach((element) => {
            element.style.width = `${clampPercent(element.dataset.progress)}%`
        })
    }

    function hydrateProgressRings(root = document) {
        root.querySelectorAll('[data-progress-ring]').forEach((element) => {
            const value = clampPercent(element.dataset.progressRing)
            element.setAttribute('stroke-dasharray', `${value} 100`)
        })
    }

    function resetDependentFields(control) {
        const form = control.form
        const specification = control.dataset.kaoriResetFields

        if (!form || !specification) return

        for (const entry of specification.split(',')) {
            const [rawName, ...rawValue] = entry.split('=')
            const name = rawName.trim()
            if (!name) continue

            const field = form.elements.namedItem(name)
            if (!field || (typeof RadioNodeList !== 'undefined' && field instanceof RadioNodeList)) continue

            field.value = rawValue.join('=').trim()
        }
    }

    function stabilizeAnalyticsExpandables(root) {
        const candidate = root || document
        const connectedCandidate = candidate.isConnected ? candidate : document
        const expandableRoots = []

        if (connectedCandidate?.matches?.('[x-data]')) expandableRoots.push(connectedCandidate)
        connectedCandidate?.querySelectorAll?.('[x-data]').forEach((element) => expandableRoots.push(element))

        if (window.Alpine) {
            expandableRoots.forEach((element) => {
                if (element.isConnected && !element._x_dataStack) window.Alpine.initTree(element)
            })
        }

        window.dispatchEvent(new CustomEvent('kaori:analytics-collapse-details'))
    }

    function stabilizeAnalyticsTabsets(root) {
        const candidate = root || document
        const connectedCandidate = candidate.isConnected ? candidate : document
        const tabsets = []

        if (connectedCandidate?.matches?.('[data-analytics-tabset]')) {
            tabsets.push(connectedCandidate)
        }
        connectedCandidate?.querySelectorAll?.('[data-analytics-tabset]').forEach((tabset) => tabsets.push(tabset))

        tabsets.forEach((tabset) => {
            if (!tabset?.isConnected) return

            const buttons = analyticsTabButtons(tabset)
            const allowedTabs = buttons.map((button) => button.dataset.analyticsTabButton).filter(Boolean)
            const tabsetId = tabset.dataset.analyticsTabsetId || tabset.id || 'default'
            const activeTab = requestedAnalyticsTab(allowedTabs, tabset.dataset.defaultTab, tabsetId)

            setAnalyticsTab(tabset, activeTab, { persist: false })
        })
    }

    function hydrateAnalyticsUi(root = document) {
        hydrateProgressBars(root)
        hydrateProgressRings(root)

        if (window.renderKaoriIcons) {
            window.renderKaoriIcons()
        } else if (window.lucide) {
            window.lucide.createIcons()
        }
    }

    function byId(id) {
            return document.getElementById(id);
        }
    
        function getPage(tracker) {
            return tracker ? byId(tracker.dataset.analyticsPageId || '') : null;
        }
    
        function getTrackedSections(tracker) {
            var page = getPage(tracker);
            if (!page || !tracker) {
                return [];
            }
    
            var selector = '[data-analytics-lazy-section="' + tracker.id + '"]';
            return Array.prototype.slice.call(page.querySelectorAll(selector));
        }
    
        function getTrackerForElement(element) {
            if (!element || !element.closest) {
                return null;
            }
    
            var tracked = element.closest('[data-analytics-lazy-section], [data-analytics-load-section]');
            if (tracked) {
                var trackerId = tracked.dataset.analyticsLazySection || tracked.dataset.analyticsLoadSection;
                return byId(trackerId);
            }
    
            var page = element.closest('[data-analytics-page-tracker]');
            if (page && page.dataset.analyticsPageRequestTracking !== 'false') {
                return byId(page.dataset.analyticsPageTracker);
            }
    
            return null;
        }
    
        function getSectionFromEvent(event) {
            var element = event.detail && event.detail.elt ? event.detail.elt : event.target;
            if (!element || !element.closest) {
                return null;
            }
    
            return element.closest('[data-analytics-lazy-section], [data-analytics-load-section]');
        }
    
        function setProgress(tracker, done, total, active) {
            if (!tracker) {
                return;
            }
    
            var title = tracker.querySelector('[data-analytics-load-title]');
            var description = tracker.querySelector('[data-analytics-load-description]');
            var counter = tracker.querySelector('[data-analytics-load-counter]');
            var progress = tracker.querySelector('[data-analytics-load-progress]');
            var percent = total > 0 ? Math.max(4, Math.round((done / total) * 100)) : (active ? 42 : 100);
    
            tracker.classList.remove('hidden');
    
            if (counter) {
                counter.textContent = total > 0 ? done + '/' + total + ' sections' : (active ? 'Loading' : 'Complete');
            }
            if (progress) {
                progress.style.width = percent + '%';
            }
    
            if (!active && (total === 0 || done >= total)) {
                if (title) {
                    title.textContent = tracker.dataset.analyticsCompleteTitle || 'Analytics page fully loaded';
                }
                if (description) {
                    description.textContent = tracker.dataset.analyticsCompleteDescription || 'All tracked analytics sections have finished loading.';
                }
                tracker.dataset.analyticsLoadState = 'complete';
                window.setTimeout(function () {
                    if (tracker.dataset.analyticsLoadState === 'complete') {
                        tracker.classList.add('hidden');
                    }
                }, 2200);
            } else {
                if (title) {
                    title.textContent = tracker.dataset.analyticsTitle || 'Loading analytics page';
                }
                if (description) {
                    description.textContent = tracker.dataset.analyticsDescription || 'Loading analytics sections in the background.';
                }
                tracker.dataset.analyticsLoadState = 'loading';
            }
        }
    
        function updateTracker(tracker) {
            if (!tracker) {
                return;
            }
    
            var sections = getTrackedSections(tracker);
            var active = parseInt(tracker.dataset.analyticsActiveRequests || '0', 10) > 0;
    
            if (!sections.length && !active) {
                return;
            }
    
            var done = sections.filter(function (section) {
                return section.dataset.analyticsLoaded === 'true' || section.dataset.analyticsLoadFailed === 'true';
            }).length;
    
            setProgress(tracker, done, sections.length, active);
        }
    
        function initTracker(tracker) {
            if (!tracker) {
                return;
            }
    
            var sections = getTrackedSections(tracker);
            tracker.dataset.analyticsActiveRequests = tracker.dataset.analyticsActiveRequests || '0';
    
            sections.forEach(function (section) {
                if (section.dataset.analyticsLoaded !== 'true' && section.dataset.analyticsLoadFailed !== 'true') {
                    section.dataset.analyticsLoaded = 'false';
                    section.dataset.analyticsLoadFailed = 'false';
                }
            });
    
            if (sections.length) {
                updateTracker(tracker);
            }
        }
    
        function initAllTrackers() {
            Array.prototype.slice.call(document.querySelectorAll('[data-analytics-load-tracker="true"]')).forEach(initTracker);
        }
    
        window.kaoriInitAnalyticsLoadTrackers = initAllTrackers;
    
        if (!window.kaoriAnalyticsLoadTrackerBound) {
            window.kaoriAnalyticsLoadTrackerBound = true;
    
            document.body.addEventListener('htmx:beforeRequest', function (event) {
                var tracker = getTrackerForElement(event.detail && event.detail.elt ? event.detail.elt : event.target);
                if (!tracker) {
                    return;
                }
    
                var active = parseInt(tracker.dataset.analyticsActiveRequests || '0', 10);
                tracker.dataset.analyticsActiveRequests = String(active + 1);
                updateTracker(tracker);
            });
    
            document.body.addEventListener('htmx:afterSettle', function (event) {
                var section = getSectionFromEvent(event);
                var tracker = getTrackerForElement(event.detail && event.detail.elt ? event.detail.elt : event.target);
    
                if (section) {
                    section.dataset.analyticsLoaded = 'true';
                }
    
                if (tracker) {
                    var active = parseInt(tracker.dataset.analyticsActiveRequests || '0', 10);
                    tracker.dataset.analyticsActiveRequests = String(Math.max(active - 1, 0));
                    updateTracker(tracker);
                }
    
                initAllTrackers();
            });
    
            ['htmx:responseError', 'htmx:sendError', 'htmx:timeout'].forEach(function (eventName) {
                document.body.addEventListener(eventName, function (event) {
                    var section = getSectionFromEvent(event);
                    var tracker = getTrackerForElement(event.detail && event.detail.elt ? event.detail.elt : event.target);
    
                    if (section) {
                        section.dataset.analyticsLoadFailed = 'true';
                    }
    
                    if (tracker) {
                        var active = parseInt(tracker.dataset.analyticsActiveRequests || '0', 10);
                        tracker.dataset.analyticsActiveRequests = String(Math.max(active - 1, 0));
                        updateTracker(tracker);
                    }
                });
            });
        }
    
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initAllTrackers);
        } else {
            initAllTrackers();
        }

    document.addEventListener(
        'change',
        (event) => {
            const control = event.target.closest('[data-kaori-reset-fields]')
            if (control) resetDependentFields(control)
        },
        true
    )

    document.addEventListener(
        'click',
        (event) => {
            const button = event.target.closest?.('[data-analytics-tab-button]')
            if (!button) return

            const tabset = button.closest('[data-analytics-tabset]')
            if (!tabset) return

            event.preventDefault()
            setAnalyticsTab(tabset, button.dataset.analyticsTabButton)
        },
        true
    )

    document.addEventListener(
        'keydown',
        (event) => {
            const button = event.target.closest?.('[data-analytics-tab-button]')
            if (!button || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return

            const tabset = button.closest('[data-analytics-tabset]')
            if (!tabset) return

            const buttons = analyticsTabButtons(tabset)
            const currentIndex = buttons.indexOf(button)
            if (currentIndex < 0) return

            event.preventDefault()
            let nextIndex = currentIndex
            if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % buttons.length
            if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + buttons.length) % buttons.length
            if (event.key === 'Home') nextIndex = 0
            if (event.key === 'End') nextIndex = buttons.length - 1

            const nextButton = buttons[nextIndex]
            setAnalyticsTab(tabset, nextButton.dataset.analyticsTabButton, { focus: true })
        },
        true
    )

    document.addEventListener('DOMContentLoaded', () => {
        hydrateAnalyticsUi()
        stabilizeAnalyticsExpandables(document)
        stabilizeAnalyticsTabsets(document)
    })
    document.body.addEventListener('htmx:load', (event) => hydrateAnalyticsUi(event.detail.elt || document))
    document.body.addEventListener('htmx:afterSwap', (event) => {
        const root = event.detail.target || document
        hydrateAnalyticsUi(root)
        stabilizeAnalyticsExpandables(root)
        stabilizeAnalyticsTabsets(root)
    })
    document.body.addEventListener('htmx:afterSettle', (event) => {
        const root = event.detail.elt || document
        hydrateAnalyticsUi(root)
        stabilizeAnalyticsExpandables(root)
        stabilizeAnalyticsTabsets(root)
    })
})()
