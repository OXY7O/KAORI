;(function () {
    'use strict'

    function parseBootstrap(documentRoot) {
        const bootstrap = documentRoot.getElementById('reports-generate-bootstrap')
        if (!bootstrap) {
            return null
        }

        try {
            return JSON.parse(bootstrap.textContent || '{}')
        } catch (error) {
            console.error('Unable to parse Reports Generate bootstrap state.', error)
            return null
        }
    }

    function initReportsGenerate(documentRoot) {
        const generateForm = documentRoot.getElementById('generate-report-form')
        if (!generateForm || generateForm.hasAttribute('data-reports-generate-initialized')) {
            return
        }

        const bootstrap = parseBootstrap(documentRoot)
        if (!bootstrap) {
            return
        }

        generateForm.setAttribute('data-reports-generate-initialized', 'true')

        const defaultSectionsByReportType = bootstrap.default_sections_by_report_type || {}
        const sectionOptionsByReportType = bootstrap.section_options_by_report_type || {}
        const reportTypeOptions = bootstrap.report_type_options || []
        const namespaceOptionsByCluster = bootstrap.namespace_options_by_cluster || {}
        const hasRegisteredClusters = Boolean(bootstrap.has_clusters)
        const hasObjectStorageSystems = Boolean(bootstrap.has_object_storage_systems)
        const initialSelectedSections = Array.isArray(bootstrap.initial_sections) ? bootstrap.initial_sections : []
        const initialNamespace = bootstrap.initial_namespace || ''

        const reportTypeSelect = documentRoot.getElementById('report-type-select')
        const periodSelect = documentRoot.getElementById('period-select')
        const periodModeLabel = documentRoot.getElementById('period-mode-label')
        const outputFormatSelect = documentRoot.getElementById('output-format-select')
        const outputFormatContract = documentRoot.getElementById('output-format-contract')
        const outputFormatDefault = documentRoot.getElementById('output-format-default')
        const outputFormatSelected = documentRoot.getElementById('output-format-selected')
        const outputFormatPurpose = documentRoot.getElementById('output-format-purpose')
        const clusterSelect = documentRoot.getElementById('cluster-select')
        const namespaceSelect = documentRoot.getElementById('namespace-select')
        const objectStorageSystemSelect = documentRoot.getElementById('object-storage-system-select')
        const kubernetesScopeFields = documentRoot.getElementById('kubernetes-scope-fields')
        const objectStorageScopeFields = documentRoot.getElementById('object-storage-scope-fields')
        const scopeTipCopy = documentRoot.getElementById('scope-tip-copy')
        const namespaceOptionCount = documentRoot.getElementById('namespace-option-count')
        const reportNameInput = documentRoot.getElementById('report-name-input')
        const generateButton = documentRoot.getElementById('generate-report-button')
        const storageGenerationReady = Boolean(bootstrap.generation_allowed)
        const selectedSectionList = documentRoot.getElementById('selected-section-list')
        const selectedSectionCountBadge = documentRoot.getElementById('selected-section-count-badge')
        const selectedSectionValidation = documentRoot.getElementById('selected-section-validation')
        const selectAllSectionsButton = documentRoot.getElementById('select-all-sections')
        const resetDefaultSectionsButton = documentRoot.getElementById('reset-default-sections')
        const selectedReportLabel = documentRoot.getElementById('selected-report-label')
        const selectedReportDescription = documentRoot.getElementById('selected-report-description')
        const selectedReportScope = documentRoot.getElementById('selected-report-scope')
        const selectedReportCount = documentRoot.getElementById('selected-report-count')
        const previewReportType = documentRoot.getElementById('preview-report-type')
        const previewReportDescription = documentRoot.getElementById('preview-report-description')
        const previewReportIcon = documentRoot.getElementById('preview-report-icon')
        const previewReportName = documentRoot.getElementById('preview-report-name')
        const previewCluster = documentRoot.getElementById('preview-cluster')
        const previewNamespace = documentRoot.getElementById('preview-namespace')
        const previewPeriod = documentRoot.getElementById('preview-period')
        const previewSections = documentRoot.getElementById('preview-sections')
        const previewIncludedSections = documentRoot.getElementById('preview-included-sections')
        const previewOutputFormat = documentRoot.getElementById('preview-output-format')
        const previewReportScopeRequirement = documentRoot.getElementById('preview-report-scope-requirement')
        const previewReportSectionCount = documentRoot.getElemntById('preview-report-section-count')
        const previewEligibilityStatus = documentRoot.getElementById('preview-eligibility-status')
        const previewEligibilityIcon = documentRoot.getElementById('preview-eligibility-icon')
        const previewEligibilityLabel = documentRoot.getElementById('preview-eligibility-label')
        const previewNextStepIcon = documentRoot.getElementById('preview-next-step-icon')
        const previewNextStepTitle = documentRoot.getElementById('preview-next-step-title')
        const previewNextStepDescription = documentRoot.getElementById('preview-next-step-description')
        const readinessScopeIcon = documentRoot.getElementById('readiness-scope-icon')
        const readinessScopeStatus = documentRoot.getElementById('readiness-scope-status')
        const readinessScopeDescription = documentRoot.getElementById('readiness-scope-description')
        const readinessSectionsIcon = documentRoot.getElementById('readiness-sections-icon')
        const readinessSectionsStatus = documentRoot.getElementById('readiness-sections-status')
        const readinessSectionsDescription = documentRoot.getElementById('readiness-sections-description')
        const readinessOverallStatus = documentRoot.getElementById('readiness-overall-status')
        const readinessOverallIcon = documentRoot.getElementById('readiness-overall-icon')
        const readinessOverallLabel = documentRoot.getElementById('readiness-overall-label')
        const readinessSummary = documentRoot.getElementById('readiness-summary')
        const readinessSummaryIcon = documentRoot.getElementById('readiness-summary-icon')
        const readinessSummaryText = documentRoot.getElementById('readiness-summary-text')
        const wizardPanels = Array.from(documentRoot.querySelectorAll('[data-wizard-panel]'))
        const wizardStepButtons = Array.from(documentRoot.querySelectorAll('[data-wizard-step-button]'))
        const wizardBackButton = documentRoot.getElementById('wizard-back-button')
        const wizardNextButton = documentRoot.getElementById('wizard-next-button')
        const wizardFooterTitle = documentRoot.getElementById('wizard-footer-title')
        const wizardFooterDescription = documentRoot.getElementById('wizard-footer-description')
        const wizardScopeValidation = documentRoot.getElementById('wizard-scope-validation')
        const wizardContractDomain = documentRoot.getElementById('wizard-contract-domain')
        const wizardContractScope = documentRoot.getElementById('wizard-contract-scope')
        const wizardContractFamily = documentRoot.getElementById('wizard-contract-family')
        const wizardContractFormat = documentRoot.getElementById('wizard-contract-format')
        const wizardContentGuidance = documentRoot.getElementById('wizard-content-guidance')

        if (!reportTypeSelect || !clusterSelect || !namespaceSelect || !selectedSectionList) {
            generateForm.removeAttribute('data-reports-generate-initialized')
            return
        }

        const wizardInitialStep = Number(generateForm.dataset.wizardInitialStep || '1')
        let currentWizardStep = Math.min(5, Math.max(1, wizardInitialStep))
        let highestVisitedWizardStep = currentWizardStep
        let overallRequestReady = Boolean(bootstrap.initial_request_ready)

        const selectedSectionsByReportType = {}
        Object.keys(defaultSectionsByReportType).forEach(function (reportType) {
            selectedSectionsByReportType[reportType] = defaultSectionsByReportType[reportType].slice()
        })

        if (initialSelectedSections.length > 0) {
            selectedSectionsByReportType[reportTypeSelect.value] = initialSelectedSections.slice()
        }

        function setReadinessItemTone(icon, status, isReady) {
            if (icon) {
                icon.className = isReady
                    ? 'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-status-normal-soft text-status-normal'
                    : 'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-status-warning-soft text-status-warning'
            }

            if (!status) {
                return
            }

            status.className = isReady
                ? 'inline-flex min-h-6 shrink-0 items-center gap-1 rounded-md border border-status-normal-border bg-status-normal-soft px-2 py-0.5 text-xs font-semibold leading-4 text-status-normal-text'
                : 'inline-flex min-h-6 shrink-0 items-center gap-1 rounded-md border border-status-warning-border bg-status-warning-soft px-2 py-0.5 text-xs font-semibold leading-4 text-status-warning-text'

            const statusIcon = status.querySelector('[data-readiness-status-icon]')
            if (statusIcon) {
                statusIcon.setAttribute('data-lucide', isReady ? 'check' : 'triangle-alert')
                statusIcon.className = isReady
                    ? 'h-3 w-3 shrink-0 text-status-normal'
                    : 'h-3 w-3 shrink-0 text-status-warning'
            }
        }

        function setReadinessStatusLabel(status, label) {
            if (!status) {
                return
            }
            const statusLabel = status.querySelector('[data-readiness-status-label]')
            if (statusLabel) {
                statusLabel.textContent = label
            }
        }

        function syncWizardNavigation() {
            wizardStepButtons.forEach(function (button) {
                const step = Number(button.dataset.wizardStepButton || '1')
                const isCurrent = step === currentWizardStep
                const isVisited = step <= highestVisitedWizardStep
                const isReady = wizardStepIsReady(step)
                button.disabled = !isVisited
                button.setAttribute('aria-current', isCurrent ? 'step' : 'false')
                button.className = isCurrent
                    ? 'flex w-full items-center gap-2 rounded-lg border border-kaori-primary/40 bg-kaori-soft px-3 py-2.5 text-left transition'
                    : 'flex w-full items-center gap-2 rounded-lg border border-outline-subtle bg-surface-card px-3 py-2.5 text-left transition hover:border-kaori-primary/40 disabled:cursor-not-allowed disabled:opacity-60'

                const marker = button.querySelector('[data-wizard-step-marker]')
                if (marker) {
                    marker.className = isCurrent
                        ? 'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-kaori-primary/30 bg-surface-card text-xs font-semibold text-kaori-primary'
                        : isVisited && isReady
                            ? 'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-status-normal-border bg-status-normal-soft text-xs font-semibold text-status-normal-text'
                            : 'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-outline-default bg-surface-hover text-xs font-semibold text-content-secondary'
                }

                const state = button.querySelector('[data-wizard-step-state]')
                if (state) {
                    state.textContent = wizardStepStateLabel(step, isCurrent, isVisited)
                }
            })
        }

        function syncOverallReadiness(isReady) {
            overallRequestReady = isReady
            const readyStatusClasses =
                'inline-flex min-h-6 shrink-0 items-center gap-1 rounded-md border border-status-normal-border bg-status-normal-soft px-2 py-0.5 text-xs font-semibold leading-4 text-status-normal-text'
            const warningStatusClasses =
                'inline-flex min-h-6 shrink-0 items-center gap-1 rounded-md border border-status-warning-border bg-status-warning-soft px-2 py-0.5 text-xs font-semibold leading-4 text-status-warning-text'

            if (readinessOverallStatus) {
                readinessOverallStatus.className = isReady ? readyStatusClasses : warningStatusClasses
            }
            if (readinessOverallIcon) {
                readinessOverallIcon.setAttribute('data-lucide', isReady ? 'circle-check' : 'triangle-alert')
                readinessOverallIcon.className = isReady
                    ? 'h-3 w-3 shrink-0 text-status-normal'
                    : 'h-3 w-3 shrink-0 text-status-warning'
            }
            if (readinessOverallLabel) {
                readinessOverallLabel.textContent = isReady ? 'Ready to Queue' : 'Action Required'
            }
            if (readinessSummary) {
                readinessSummary.className = isReady
                    ? 'flex min-w-0 items-start gap-2 text-xs leading-5 text-status-normal-text'
                    : 'flex min-w-0 items-start gap-2 text-xs leading-5 text-status-warning-text'
            }
            if (readinessSummaryIcon) {
                readinessSummaryIcon.setAttribute('data-lucide', isReady ? 'circle-check' : 'circle-alert')
                readinessSummaryIcon.className = isReady
                    ? 'mt-0.5 h-4 w-4 shrink-0 text-