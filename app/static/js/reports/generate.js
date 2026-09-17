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
        const previewReportSectionCount = documentRoot.getElementById('preview-report-section-count')
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
                    ? 'mt-0.5 h-4 w-4 shrink-0 text-status-normal'
                    : 'mt-0.5 h-4 w-4 shrink-0 text-status-warning'
            }
            if (readinessSummaryText) {
                readinessSummaryText.textContent = isReady
                    ? 'Scope and artifact requirements are valid. The request is ready to queue.'
                    : storageGenerationReady
                      ? 'Resolve the required scope or section checks before creating the request.'
                      : 'Artifact storage is unavailable. Restore storage connectivity before creating a report.'
            }
            if (previewEligibilityStatus) {
                previewEligibilityStatus.className = isReady ? readyStatusClasses : warningStatusClasses
            }
            if (previewEligibilityIcon) {
                previewEligibilityIcon.setAttribute('data-lucide', isReady ? 'circle-check' : 'triangle-alert')
                previewEligibilityIcon.className = isReady
                    ? 'h-3 w-3 shrink-0 text-status-normal'
                    : 'h-3 w-3 shrink-0 text-status-warning'
            }
            if (previewEligibilityLabel) {
                previewEligibilityLabel.textContent = isReady ? 'Ready to Queue' : 'Action Required'
            }
            if (previewNextStepIcon) {
                const icon = previewNextStepIcon.querySelector('[data-lucide]')
                if (icon) {
                    icon.setAttribute('data-lucide', isReady ? 'arrow-right' : 'list-checks')
                }
            }
            if (previewNextStepTitle) {
                previewNextStepTitle.textContent = isReady ? 'Ready to Queue' : 'Complete Required Inputs'
            }
            if (previewNextStepDescription) {
                previewNextStepDescription.textContent = isReady
                    ? 'The governed request will be saved and queued on the canonical Reports worker.'
                    : storageGenerationReady
                      ? 'Resolve the required scope or section selection before continuing.'
                      : 'Restore artifact storage connectivity before creating and queueing a report.'
            }
            syncWizardNavigation()
        }

        function getReportTypeOption() {
            return (
                reportTypeOptions.find(function (item) {
                    return item.value === reportTypeSelect.value
                }) || reportTypeOptions[0]
            )
        }

        function getSelectedSections() {
            return selectedSectionsByReportType[reportTypeSelect.value] || []
        }

        function setSelectedSections(sections) {
            selectedSectionsByReportType[reportTypeSelect.value] = sections.slice()
        }

        function updateSelectedSectionFromCheckbox(checkbox) {
            const selected = new Set(getSelectedSections())
            if (checkbox.checked) {
                selected.add(checkbox.value)
            } else {
                selected.delete(checkbox.value)
            }
            setSelectedSections(Array.from(selected))
            syncSectionCount()
        }

        function syncSectionCount() {
            const selectedSections = getSelectedSections()
            const selectedCount = selectedSections.length
            const sectionLabel = selectedCount === 1 ? 'Section' : 'Sections'
            const sectionOptions = sectionOptionsByReportType[reportTypeSelect.value] || []
            const selectedLabels = sectionOptions
                .filter(function (section) {
                    return selectedSections.includes(section.value)
                })
                .map(function (section) {
                    return section.label
                })
            const reportType = getReportTypeOption()
            const inventoryContractLocked = reportType && reportType.family === 'inventory'
            const sectionStateLabel = inventoryContractLocked ? 'Locked' : 'Selected'

            if (selectedSectionCountBadge) {
                selectedSectionCountBadge.textContent = selectedCount + ' ' + sectionStateLabel
            }
            if (selectedReportCount) {
                selectedReportCount.textContent = selectedCount + ' ' + sectionLabel
            }
            if (previewReportSectionCount) {
                previewReportSectionCount.textContent = selectedCount + ' ' + sectionLabel
            }
            if (previewSections) {
                previewSections.textContent = selectedCount + ' ' + sectionStateLabel
            }
            if (previewIncludedSections) {
                previewIncludedSections.textContent = selectedLabels.length
                    ? selectedLabels.join(', ')
                    : 'No sections selected.'
            }
            if (selectedSectionValidation) {
                selectedSectionValidation.classList.toggle('hidden', selectedCount > 0)
            }
            setReadinessItemTone(readinessSectionsIcon, readinessSectionsStatus, selectedCount > 0)
            setReadinessStatusLabel(readinessSectionsStatus, selectedCount > 0 ? 'Content Ready' : 'Selection Required')
            if (readinessSectionsDescription) {
                readinessSectionsDescription.textContent =
                    selectedCount > 0
                        ? 'At least one report section is selected for this request.'
                        : 'Select at least one report section before creating the request.'
            }
            syncClusterGuard()
        }

        function setElementVisibility(element, isVisible) {
            if (!element) {
                return
            }
            element.classList.toggle('hidden', !isVisible)
        }

        function renderSectionList() {
            const reportType = getReportTypeOption()
            const inventoryContractLocked = reportType && reportType.family === 'inventory'
            if (inventoryContractLocked) {
                setSelectedSections((defaultSectionsByReportType[reportTypeSelect.value] || []).slice())
            }
            const selectedSections = new Set(getSelectedSections())
            const selectedOptions = sectionOptionsByReportType[reportTypeSelect.value] || []

            selectedSectionList.className = 'mt-3 grid gap-2 sm:grid-cols-2'
            selectedSectionList.replaceChildren()

            selectedOptions.forEach(function (section) {
                if (inventoryContractLocked) {
                    const row = document.createElement('div')
                    row.className =
                        'flex min-w-0 items-start gap-2.5 rounded-lg border border-outline-subtle bg-surface-hover px-3 py-3'
                    const marker = document.createElement('span')
                    marker.className =
                        'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-kaori-soft text-kaori-primary'
                    const markerIcon = document.createElement('i')
                    markerIcon.setAttribute('data-lucide', 'file-spreadsheet')
                    markerIcon.className = 'h-3.5 w-3.5'
                    markerIcon.setAttribute('aria-hidden', 'true')
                    marker.appendChild(markerIcon)
                    const input = document.createElement('input')
                    input.type = 'hidden'
                    input.name = 'sections'
                    input.value = section.value
                    const content = document.createElement('div')
                    content.className = 'min-w-0'
                    const title = document.createElement('p')
                    title.className = 'text-sm font-semibold text-content-primary'
                    title.textContent = section.label
                    const description = document.createElement('p')
                    description.className = 'mt-0.5 text-xs leading-5 text-content-muted'
                    description.textContent = section.description
                    content.appendChild(title)
                    content.appendChild(description)
                    row.appendChild(marker)
                    row.appendChild(input)
                    row.appendChild(content)
                    selectedSectionList.appendChild(row)
                    return
                }

                const label = document.createElement('label')
                label.className =
                    'flex min-w-0 cursor-pointer items-start gap-2.5 rounded-lg border border-outline-subtle bg-surface-card px-3 py-3 transition hover:border-kaori-primary/40 hover:bg-kaori-soft/30'
                const input = document.createElement('input')
                input.type = 'checkbox'
                input.name = 'sections'
                input.value = section.value
                input.checked = selectedSections.has(section.value)
                input.className =
                    'mt-0.5 h-4 w-4 shrink-0 rounded border-outline-default bg-surface-card text-kaori-primary focus:ring-kaori-primary/20'
                input.addEventListener('change', function () {
                    updateSelectedSectionFromCheckbox(input)
                })
                const content = document.createElement('span')
                content.className = 'min-w-0'
                const title = document.createElement('span')
                title.className = 'block text-sm font-semibold text-content-primary'
                title.textContent = section.label
                const description = document.createElement('span')
                description.className = 'mt-0.5 block text-xs leading-5 text-content-muted'
                description.textContent = section.description
                content.appendChild(title)
                content.appendChild(description)
                label.appendChild(input)
                label.appendChild(content)
                selectedSectionList.appendChild(label)
            })

            const selectionActions = documentRoot.getElementById('section-selection-actions')
            const contractNote = documentRoot.getElementById('section-contract-note')
            setElementVisibility(selectionActions, !inventoryContractLocked)
            if (contractNote) {
                contractNote.textContent = inventoryContractLocked
                    ? 'Inventory workbook structure is locked by the report contract.'
                    : 'Choose the analytics sections included in this artifact.'
            }
            syncSectionCount()
            if (window.lucide) {
                window.lucide.createIcons()
            }
        }

        function syncOutputFormatMode() {
            if (!outputFormatSelect) {
                return
            }
            const reportType = getReportTypeOption()
            const allowedFormats =
                reportType && Array.isArray(reportType.allowed_formats) ? reportType.allowed_formats : []
            const primaryFormat = reportType && reportType.primary_format ? reportType.primary_format : ''
            Array.from(outputFormatSelect.options).forEach(function (option) {
                const isAllowed = allowedFormats.includes(option.value)
                option.disabled = !isAllowed
                option.hidden = !isAllowed
            })
            if (!allowedFormats.includes(outputFormatSelect.value)) {
                outputFormatSelect.value = primaryFormat
            }
            if (outputFormatContract) {
                outputFormatContract.textContent = allowedFormats
                    .map(function (format) {
                        return format.toUpperCase()
                    })
                    .join(' · ')
            }
            if (outputFormatDefault) {
                outputFormatDefault.textContent = primaryFormat ? primaryFormat.toUpperCase() : '—'
            }
            const selectedFormat = outputFormatSelect.value
            if (outputFormatSelected) {
                if (selectedFormat === 'csv') {
                    outputFormatSelected.textContent = 'CSV Export'
                } else if (selectedFormat === 'xlsx') {
                    outputFormatSelected.textContent = 'XLSX Workbook'
                } else {
                    outputFormatSelected.textContent = 'PDF Publication'
                }
            }
            if (outputFormatPurpose) {
                if (selectedFormat === 'csv') {
                    outputFormatPurpose.textContent =
                        'Flat machine-readable evidence export for downstream analysis and audit.'
                } else if (selectedFormat === 'xlsx') {
                    outputFormatPurpose.textContent =
                        reportType && reportType.family === 'analytics'
                            ? 'Governed analytical workbook for drill-down, filtering, trends, and evidence review.'
                            : 'Governed workbook preserving inventory structure and tabular review.'
                } else {
                    outputFormatPurpose.textContent =
                        'Governed analytical publication for review, evidence, and operational communication.'
                }
            }
            if (previewOutputFormat && outputFormatSelect.options[outputFormatSelect.selectedIndex]) {
                previewOutputFormat.textContent =
                    outputFormatSelect.options[outputFormatSelect.selectedIndex].text.trim()
            }
        }

        function syncPeriodMode() {
            if (!periodSelect) {
                return
            }
            const reportType = getReportTypeOption()
            const isInventoryReport = reportType && reportType.family === 'inventory'
            Array.from(periodSelect.options).forEach(function (option) {
                option.hidden = isInventoryReport ? option.value !== 'snapshot' : option.value === 'snapshot'
            })
            if (isInventoryReport) {
                periodSelect.value = 'snapshot'
            } else if (periodSelect.value === 'snapshot') {
                periodSelect.value = '30d'
            }
            if (periodModeLabel) {
                periodModeLabel.textContent = isInventoryReport ? 'Snapshot' : 'Time Range'
            }
            if (previewPeriod && periodSelect.options[periodSelect.selectedIndex]) {
                previewPeriod.textContent = periodSelect.options[periodSelect.selectedIndex].text.trim()
            }
        }

        function getDefaultReportName() {
            const reportType = getReportTypeOption()
            const periodLabel =
                periodSelect && periodSelect.options[periodSelect.selectedIndex]
                    ? periodSelect.options[periodSelect.selectedIndex].text.trim()
                    : 'Report Period'
            return reportType.label + ' - ' + periodLabel
        }

        function syncPreviewReportName() {
            if (!previewReportName) {
                return
            }
            previewReportName.textContent =
                reportNameInput && reportNameInput.value.trim() ? reportNameInput.value.trim() : getDefaultReportName()
        }

        function syncReportTypeSummary() {
            const reportType = getReportTypeOption()
            const selectedSections = getSelectedSections()
            const sectionLabel = selectedSections.length === 1 ? 'Section' : 'Sections'
            const scopeLabel =
                reportType.scope_asset_type === 'object_storage_system' ? 'Object Storage System' : 'Kubernetes Cluster'
            if (selectedReportLabel) selectedReportLabel.textContent = reportType.label
            if (selectedReportDescription) selectedReportDescription.textContent = reportType.description
            if (selectedReportScope) selectedReportScope.textContent = scopeLabel
            if (selectedReportCount) selectedReportCount.textContent = selectedSections.length + ' ' + sectionLabel
            if (wizardContractDomain) {
                wizardContractDomain.textContent = (reportType.domain || 'kubernetes')
                    .replace(/_/g, ' ')
                    .replace(/\b\w/g, function (character) {
                        return character.toUpperCase()
                    })
            }
            if (wizardContractScope) wizardContractScope.textContent = scopeLabel
            if (wizardContractFamily)
                wizardContractFamily.textContent = reportType.family === 'inventory' ? 'Inventory' : 'Analytics'
            if (wizardContractFormat)
                wizardContractFormat.textContent = (reportType.primary_format || 'pdf').toUpperCase()
            if (wizardContentGuidance) {
                wizardContentGuidance.textContent =
                    reportType.family === 'inventory'
                        ? 'Inventory content is contract-locked so workbook structure stays consistent across generations.'
                        : 'Analytics content is selectable. At least one published section must remain selected before the request can be queued.'
            }
            if (previewReportType) previewReportType.textContent = reportType.label
            if (previewReportDescription) previewReportDescription.textContent = reportType.description
            if (previewReportScopeRequirement) previewReportScopeRequirement.textContent = scopeLabel
            if (previewReportIcon) previewReportIcon.setAttribute('data-lucide', reportType.icon || 'file-text')
            syncPreviewReportName()
        }

        function updateNamespaceOptions(selectedValue) {
            const clusterId = clusterSelect.value
            const namespaces = namespaceOptionsByCluster[clusterId] || []
            const normalizedSelectedValue = selectedValue || ''
            namespaceSelect.replaceChildren()
            const allNamespacesOption = document.createElement('option')
            allNamespacesOption.value = ''
            allNamespacesOption.textContent = 'All Namespaces'
            namespaceSelect.appendChild(allNamespacesOption)
            namespaces.forEach(function (namespace) {
                const option = document.createElement('option')
                option.value = namespace
                option.textContent = namespace
                namespaceSelect.appendChild(option)
            })
            if (!clusterId) {
                namespaceSelect.disabled = true
                namespaceSelect.value = ''
                if (namespaceOptionCount) {
                    namespaceOptionCount.textContent = ''
                    namespaceOptionCount.classList.add('hidden')
                }
                return
            }
            namespaceSelect.disabled = false
            namespaceSelect.value = namespaces.includes(normalizedSelectedValue) ? normalizedSelectedValue : ''
            if (namespaceOptionCount) {
                namespaceOptionCount.textContent = namespaces.length + ' available'
                namespaceOptionCount.classList.remove('hidden')
            }
        }

        function syncClusterGuard() {
            const reportType = getReportTypeOption()
            const scopeType =
                reportType && reportType.scope_asset_type ? reportType.scope_asset_type : 'kubernetes_cluster'
            const objectStorageScope = scopeType === 'object_storage_system'
            const hasSelectedSections = getSelectedSections().length > 0
            const clusterReady = hasRegisteredClusters && Boolean(clusterSelect.value)
            const objectStorageReady =
                hasObjectStorageSystems && objectStorageSystemSelect && Boolean(objectStorageSystemSelect.value)
            const scopeReady = objectStorageScope ? objectStorageReady : clusterReady
            const shouldBlock = !scopeReady || !hasSelectedSections || !storageGenerationReady

            if (wizardScopeValidation) {
                wizardScopeValidation.classList.toggle('hidden', scopeReady)
                wizardScopeValidation.textContent = objectStorageScope
                    ? 'Select one registered Object Storage system before continuing.'
                    : 'Select one validated Kubernetes cluster before continuing.'
            }
            setElementVisibility(kubernetesScopeFields, !objectStorageScope)
            setElementVisibility(objectStorageScopeFields, objectStorageScope)
            if (clusterSelect) clusterSelect.disabled = objectStorageScope
            if (namespaceSelect) namespaceSelect.disabled = objectStorageScope || !clusterSelect.value
            if (objectStorageSystemSelect) objectStorageSystemSelect.disabled = !objectStorageScope

            const clusterLabel =
                clusterSelect && clusterSelect.options[clusterSelect.selectedIndex]
                    ? clusterSelect.options[clusterSelect.selectedIndex].text.trim()
                    : 'Select Cluster'
            const systemLabel =
                objectStorageSystemSelect && objectStorageSystemSelect.options[objectStorageSystemSelect.selectedIndex]
                    ? objectStorageSystemSelect.options[objectStorageSystemSelect.selectedIndex].text.trim()
                    : 'Select Object Storage System'
            const namespaceValue =
                namespaceSelect && namespaceSelect.value
                    ? namespaceSelect.options[namespaceSelect.selectedIndex].text.trim()
                    : 'All Namespaces'

            setReadinessItemTone(readinessScopeIcon, readinessScopeStatus, scopeReady)
            setReadinessStatusLabel(
                readinessScopeStatus,
                scopeReady ? 'Scope Ready' : objectStorageScope ? 'Select Object Storage System' : 'Select Cluster'
            )
            if (readinessScopeDescription) {
                readinessScopeDescription.textContent = objectStorageScope
                    ? hasObjectStorageSystems
                        ? 'Select one registered Object Storage system for this report.'
                        : 'Register at least one Object Storage system before creating Object Storage reports.'
                    : hasRegisteredClusters
                      ? 'Select one validated Kubernetes cluster for this report.'
                      : 'Register at least one Kubernetes cluster before creating Kubernetes reports.'
            }
            if (scopeTipCopy) {
                scopeTipCopy.textContent = objectStorageScope
                    ? 'This report is bound to one registered Object Storage system; Kubernetes cluster and namespace fields are not part of the contract.'
                    : 'This report is bound to one Kubernetes cluster; namespace optionally narrows the selected cluster.'
            }
            if (selectedReportScope)
                selectedReportScope.textContent = objectStorageScope ? 'Object Storage System' : 'Kubernetes Cluster'
            if (previewReportScopeRequirement) {
                previewReportScopeRequirement.textContent = objectStorageScope
                    ? 'Object Storage System Required'
                    : 'Selected Cluster Required'
            }
            if (previewCluster) previewCluster.textContent = objectStorageScope ? systemLabel : clusterLabel
            if (previewNamespace) previewNamespace.textContent = objectStorageScope ? 'System Scope' : namespaceValue

            syncOverallReadiness(!shouldBlock)
            if (window.lucide) window.lucide.createIcons()
            if (!generateButton) return
            generateButton.disabled = shouldBlock
            const submitVisibilityClass = currentWizardStep === 5 ? 'inline-flex' : 'hidden'
            generateButton.className = shouldBlock
                ? submitVisibilityClass +
                  ' min-h-9 cursor-not-allowed items-center justify-center gap-2 rounded-lg bg-kaori-soft px-5 text-sm font-semibold text-content-muted transition focus:outline-none focus:ring-2 focus:ring-kaori-primary/20'
                : submitVisibilityClass +
                  ' min-h-9 items-center justify-center gap-2 rounded-lg bg-kaori-primary px-5 text-sm font-semibold text-white transition hover:bg-kaori-primary-dark focus:outline-none focus:ring-2 focus:ring-kaori-primary/20'
        }

        function wizardScopeIsReady() {
            const reportType = getReportTypeOption()
            if (reportType.scope_asset_type === 'object_storage_system') {
                return hasObjectStorageSystems && Boolean(objectStorageSystemSelect && objectStorageSystemSelect.value)
            }
            return hasRegisteredClusters && Boolean(clusterSelect.value)
        }

        function wizardArtifactIsReady() {
            const reportType = getReportTypeOption()
            const allowedFormats =
                reportType && Array.isArray(reportType.allowed_formats) ? reportType.allowed_formats : []
            return Boolean(outputFormatSelect && allowedFormats.includes(outputFormatSelect.value))
        }

        function wizardStepIsReady(step) {
            if (step === 1) return Boolean(reportTypeSelect.value)
            if (step === 2) return wizardScopeIsReady()
            if (step === 3) return wizardArtifactIsReady()
            if (step === 4) return getSelectedSections().length > 0
            return overallRequestReady
        }

        function wizardStepStateLabel(step, isCurrent, isVisited) {
            if (isCurrent) {
                if (step === 5) return overallRequestReady ? 'Current · Ready to Queue' : 'Current · Review Required'
                if (step === 3 && !storageGenerationReady) return 'Current · Storage Needs Review'
                return wizardStepIsReady(step) ? 'Current · Ready' : 'Current · Action Required'
            }
            if (isVisited) {
                if (step === 3 && !storageGenerationReady) return 'Storage Needs Review'
                return wizardStepIsReady(step) ? 'Complete' : 'Needs Attention'
            }
            const pendingLabels = {
                1: 'Choose report',
                2: 'Bind target',
                3: 'Choose output',
                4: 'Select sections',
                5: 'Validate request',
            }
            return pendingLabels[step] || 'Pending'
        }

        function showWizardStep(step, focusPanel) {
            const nextStep = Math.min(5, Math.max(1, step))
            if (nextStep > highestVisitedWizardStep) return
            currentWizardStep = nextStep
            wizardPanels.forEach(function (panel) {
                panel.classList.toggle('hidden', Number(panel.dataset.wizardPanel) !== currentWizardStep)
            })
            if (wizardBackButton) {
                wizardBackButton.classList.toggle('hidden', currentWizardStep === 1)
                wizardBackButton.classList.toggle('inline-flex', currentWizardStep !== 1)
            }
            if (wizardNextButton) {
                wizardNextButton.classList.toggle('hidden', currentWizardStep === 5)
                wizardNextButton.classList.toggle('inline-flex', currentWizardStep !== 5)
            }
            if (generateButton) {
                generateButton.classList.toggle('hidden', currentWizardStep !== 5)
                generateButton.classList.toggle('inline-flex', currentWizardStep === 5)
            }
            const footerTitles = {
                1: 'Step 1 of 5 · Report Contract',
                2: 'Step 2 of 5 · Infrastructure Scope',
                3: 'Step 3 of 5 · Artifact Contract',
                4: 'Step 4 of 5 · Report Content',
                5: 'Step 5 of 5 · Review & Queue',
            }
            const footerDescriptions = {
                1: 'Choose a report contract. You can go back and change previous steps before queueing.',
                2: 'Bind the report to its required infrastructure asset and period boundary.',
                3: 'Choose an allowed artifact format and review publication readiness.',
                4: 'Confirm the contract-locked or selected section set included in the artifact.',
                5: 'Nothing has been saved yet. Review the full request, then create and queue it once.',
            }
            if (wizardFooterTitle) wizardFooterTitle.textContent = footerTitles[currentWizardStep]
            if (wizardFooterDescription) wizardFooterDescription.textContent = footerDescriptions[currentWizardStep]
            syncWizardNavigation()
            if (focusPanel) {
                const panel = wizardPanels.find(function (item) {
                    return Number(item.dataset.wizardPanel) === currentWizardStep
                })
                if (panel) {
                    panel.setAttribute('tabindex', '-1')
                    panel.focus({ preventScroll: false })
                }
            }
            if (window.lucide) window.lucide.createIcons()
        }

        function validateWizardStep(step) {
            const isReady = wizardStepIsReady(step)
            if (step === 2 && wizardScopeValidation) wizardScopeValidation.classList.toggle('hidden', isReady)
            if (step === 4 && selectedSectionValidation) selectedSectionValidation.classList.toggle('hidden', isReady)
            if (isReady) return true
            if (step === 2) {
                const reportType = getReportTypeOption()
                const target =
                    reportType.scope_asset_type === 'object_storage_system' ? objectStorageSystemSelect : clusterSelect
                if (target) target.focus()
            } else if (step === 4) {
                const firstSection = selectedSectionList.querySelector('input[type="checkbox"]')
                if (firstSection) firstSection.focus()
            }
            syncWizardNavigation()
            return false
        }

        function syncForm() {
            syncOutputFormatMode()
            syncPeriodMode()
            syncReportTypeSummary()
            renderSectionList()
            syncClusterGuard()
        }

        reportTypeSelect.addEventListener('change', function () {
            highestVisitedWizardStep = 1
            syncForm()
            showWizardStep(1, false)
        })
        clusterSelect.addEventListener('change', function () {
            updateNamespaceOptions('')
            syncClusterGuard()
        })
        if (objectStorageSystemSelect) objectStorageSystemSelect.addEventListener('change', syncClusterGuard)
        if (outputFormatSelect) outputFormatSelect.addEventListener('change', syncOutputFormatMode)
        if (periodSelect) {
            periodSelect.addEventListener('change', function () {
                if (previewPeriod)
                    previewPeriod.textContent = periodSelect.options[periodSelect.selectedIndex].text.trim()
                syncPreviewReportName()
            })
        }
        namespaceSelect.addEventListener('change', syncClusterGuard)
        if (reportNameInput) reportNameInput.addEventListener('input', syncPreviewReportName)
        if (selectAllSectionsButton) {
            selectAllSectionsButton.addEventListener('click', function () {
                const allSections = (sectionOptionsByReportType[reportTypeSelect.value] || []).map(function (section) {
                    return section.value
                })
                setSelectedSections(allSections)
                renderSectionList()
                syncReportTypeSummary()
            })
        }
        if (resetDefaultSectionsButton) {
            resetDefaultSectionsButton.addEventListener('click', function () {
                setSelectedSections(defaultSectionsByReportType[reportTypeSelect.value] || [])
                renderSectionList()
                syncReportTypeSummary()
            })
        }
        if (wizardBackButton) {
            wizardBackButton.addEventListener('click', function () {
                showWizardStep(currentWizardStep - 1, true)
            })
        }
        if (wizardNextButton) {
            wizardNextButton.addEventListener('click', function () {
                if (!validateWizardStep(currentWizardStep)) return
                highestVisitedWizardStep = Math.max(highestVisitedWizardStep, currentWizardStep + 1)
                showWizardStep(currentWizardStep + 1, true)
            })
        }
        wizardStepButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                const step = Number(button.dataset.wizardStepButton || '1')
                if (step <= highestVisitedWizardStep) showWizardStep(step, true)
            })
        })
        generateForm.addEventListener('submit', function (event) {
            if (currentWizardStep !== 5) {
                event.preventDefault()
                if (validateWizardStep(currentWizardStep)) {
                    highestVisitedWizardStep = Math.max(highestVisitedWizardStep, currentWizardStep + 1)
                    showWizardStep(currentWizardStep + 1, true)
                }
                return
            }
            if (!overallRequestReady) {
                event.preventDefault()
                syncWizardNavigation()
            }
        })

        updateNamespaceOptions(initialNamespace)
        syncForm()
        showWizardStep(currentWizardStep, false)
        if (periodSelect && previewPeriod) {
            previewPeriod.textContent = periodSelect.options[periodSelect.selectedIndex].text.trim()
        }
        if (outputFormatSelect && previewOutputFormat) {
            previewOutputFormat.textContent = outputFormatSelect.options[outputFormatSelect.selectedIndex].text.trim()
        }
    }

    function initialize() {
        initReportsGenerate(document)
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize, { once: true })
    } else {
        initialize()
    }

    document.addEventListener('htmx:afterSwap', initialize)
})()
