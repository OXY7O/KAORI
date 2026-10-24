;(() => {
    const fieldMap = {
        requests_cpu: ['quota', 'requests.cpu'],
        limits_cpu: ['quota', 'limits.cpu'],
        requests_memory: ['quota', 'requests.memory'],
        limits_memory: ['quota', 'limits.memory'],
        pods: ['quota', 'pods'],
        persistentvolumeclaims: ['quota', 'persistentvolumeclaims'],
        requests_storage: ['quota', 'requests.storage'],
        services: ['quota', 'services'],
        configmaps: ['quota', 'configmaps'],
        secrets: ['quota', 'secrets'],
        pvc_min_storage: ['storage_policy', 'min'],
        pvc_max_storage: ['storage_policy', 'max'],
        default_request_cpu: ['limits', 'default_request', 'cpu'],
        default_cpu: ['limits', 'default', 'cpu'],
        default_request_memory: ['limits', 'default_request', 'memory'],
        default_memory: ['limits', 'default', 'memory'],
    }

    const readPath = (value, path) => path.reduce((current, key) => current?.[key], value)
    const readJson = (id) => JSON.parse(document.getElementById(id)?.textContent || '{}')

    const collectFields = (form, attribute) =>
        Object.fromEntries(
            Array.from(form.querySelectorAll(`[${attribute}]`)).map((input) => [input.getAttribute(attribute), input])
        )

    const applyValues = (fields, valueSet) => {
        for (const [name, target] of Object.entries(fields)) {
            const value = valueSet ? readPath(valueSet, fieldMap[name]) || '' : ''
            if ('value' in target) {
                target.value = value
            } else {
                target.textContent = value || '—'
            }
        }
    }

    const setReadonly = (form, fields, readonly) => {
        for (const input of Object.values(fields)) {
            if ('readOnly' in input) input.readOnly = readonly
            input.setAttribute('aria-readonly', readonly ? 'true' : 'false')
            input.dataset.locked = readonly ? 'true' : 'false'

            const wrapper = input.closest('[data-tenant-resource-field-wrap]')
            if (wrapper) wrapper.dataset.locked = readonly ? 'true' : 'false'
            const fixedLabel = wrapper?.querySelector('[data-tenant-resource-mode-fixed]')
            const customLabel = wrapper?.querySelector('[data-tenant-resource-mode-custom]')

            if (fixedLabel) fixedLabel.hidden = !readonly
            if (customLabel) customLabel.hidden = readonly
        }

        const modeBanner = form.querySelector('[data-tenant-profile-mode-banner]')
        const modeTitle = form.querySelector('[data-tenant-profile-mode-title]')
        const modeDetail = form.querySelector('[data-tenant-profile-mode-detail]')
        const fixedModeLabel = form.querySelector('[data-tenant-profile-mode-fixed-label]')
        const customModeLabel = form.querySelector('[data-tenant-profile-mode-custom-label]')
        const modeIcon = form.querySelector('[data-tenant-profile-mode-icon] [data-lucide]')

        if (modeBanner) {
            modeBanner.dataset.mode = readonly ? 'fixed' : 'custom'
            modeBanner.classList.toggle('border-kaori-primary/20', readonly)
            modeBanner.classList.toggle('bg-kaori-soft', readonly)
            modeBanner.classList.toggle('border-outline-subtle', !readonly)
            modeBanner.classList.toggle('bg-surface-card', !readonly)
        }
        if (modeTitle) modeTitle.textContent = readonly ? 'KAORI Preset · Fixed' : 'Custom · Editable'
        if (modeDetail) {
            modeDetail.textContent = readonly
                ? 'Values are fixed; Managed toggles choose which dimensions KAORI owns.'
                : 'Editable values; Managed toggles choose which dimensions KAORI owns.'
        }
        if (fixedModeLabel) fixedModeLabel.hidden = !readonly
        if (customModeLabel) customModeLabel.hidden = readonly
        if (modeIcon) modeIcon.setAttribute('data-lucide', readonly ? 'lock-keyhole' : 'pencil')

        window.lucide?.createIcons?.()
    }

    const initProfileForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const presets = readJson('tenant-resource-profile-presets')
        const classSelect = form.querySelector('[data-tenant-profile-class]')
        const basePreset = form.querySelector('[data-tenant-base-preset]')
        const basePresetWrapper = form.querySelector('[data-tenant-base-preset-wrapper]')
        const fields = collectFields(form, 'data-tenant-resource-field')
        const controls = collectFields(form, 'data-tenant-resource-control')

        const syncManagedState = () => {
            for (const [name, input] of Object.entries(fields)) {
                const managed = controls[name]?.checked !== false
                input.disabled = !managed
                input.setAttribute('aria-disabled', managed ? 'false' : 'true')
                const wrapper = input.closest('[data-tenant-resource-field-wrap]')
                if (wrapper) {
                    wrapper.dataset.controlled = managed ? 'true' : 'false'
                    wrapper.classList.toggle('opacity-60', !managed)
                }
            }
        }

        const applyProfileMode = () => {
            const profileClass = classSelect?.value || ''
            const preset = presets[profileClass]

            if (preset) {
                applyValues(fields, preset)
                setReadonly(form, fields, true)
                for (const [name, control] of Object.entries(controls)) {
                    const wrapper = fields[name]?.closest('[data-tenant-resource-field-wrap]')
                    if (wrapper?.dataset.controlRequiresValue === 'true') {
                        const available = readPath(preset, fieldMap[name]) !== undefined
                        control.checked = available
                        control.disabled = !available
                        control.setAttribute('aria-disabled', available ? 'false' : 'true')
                    } else {
                        control.disabled = false
                        control.setAttribute('aria-disabled', 'false')
                    }
                }
                if (basePreset) {
                    basePreset.value = ''
                    basePreset.disabled = true
                }
                if (basePresetWrapper) basePresetWrapper.hidden = true
                syncManagedState()
                return
            }

            setReadonly(form, fields, false)
            for (const control of Object.values(controls)) {
                control.disabled = false
                control.setAttribute('aria-disabled', 'false')
            }
            if (basePreset) basePreset.disabled = false
            if (basePresetWrapper) basePresetWrapper.hidden = false
            applyValues(fields, basePreset?.value ? presets[basePreset.value] : null)
            syncManagedState()
        }

        classSelect?.addEventListener('change', applyProfileMode)
        basePreset?.addEventListener('change', () => {
            if (classSelect?.value === 'custom') {
                const inherited = basePreset.value ? presets[basePreset.value] : null
                applyValues(fields, inherited)
                for (const [name, control] of Object.entries(controls)) {
                    const wrapper = fields[name]?.closest('[data-tenant-resource-field-wrap]')
                    if (wrapper?.dataset.controlRequiresValue === 'true') {
                        control.checked = inherited ? readPath(inherited, fieldMap[name]) !== undefined : false
                    }
                }
                syncManagedState()
            }
        })
        Object.values(controls).forEach((control) => control.addEventListener('change', syncManagedState))
        applyProfileMode()
    }

    const initAdvancedControls = (container) => {
        if (!(container instanceof HTMLElement) || container.dataset.kaoriAdvancedInitialized === 'true') return
        container.dataset.kaoriAdvancedInitialized = 'true'

        container.querySelectorAll('[data-tenant-advanced-control-group]').forEach((group) => {
            const key = group.getAttribute('data-tenant-advanced-control-group')
            const toggle = group.querySelector(`[data-tenant-advanced-control-toggle="${key}"]`)
            const fields = Array.from(group.querySelectorAll(`[data-tenant-advanced-control-field="${key}"]`))
            const statusLabel = group.querySelector('.kaori-semantic-label')
            const statusText = statusLabel?.querySelector('span:last-child')

            if (!(toggle instanceof HTMLInputElement)) return

            const syncStatus = (enabled) => {
                if (statusText) statusText.textContent = enabled ? 'Enabled' : 'Off'
                if (!statusLabel) return
                statusLabel.classList.toggle('bg-status-normal-soft', enabled)
                statusLabel.classList.toggle('text-status-normal-text', enabled)
                statusLabel.classList.toggle('bg-status-unknown-soft', !enabled)
                statusLabel.classList.toggle('text-status-unknown-text', !enabled)
            }

            const sync = () => {
                const enabled = toggle.checked
                fields.forEach((field) => {
                    field.disabled = !enabled
                    field.setAttribute('aria-disabled', enabled ? 'false' : 'true')
                })

                if (key === 'service_exposure') {
                    const profile = group.querySelector('[data-tenant-service-exposure-profile]')
                    const customFields = group.querySelectorAll('[data-tenant-service-exposure-custom-field]')
                    const custom = enabled && profile?.value === 'custom'
                    customFields.forEach((field) => {
                        field.disabled = !custom
                        field.setAttribute('aria-disabled', custom ? 'false' : 'true')
                    })
                }

                if (key === 'managed_tls') {
                    const mode = group.querySelector('[data-tenant-managed-tls-mode]')
                    const source = group.querySelector('[data-tenant-managed-tls-source]')
                    if (source instanceof HTMLInputElement) {
                        source.required = enabled && mode?.value === 'namespace_tls_compat'
                    }
                }

                if (key === 'managed_registry') {
                    const mode = group.querySelector('[data-tenant-managed-registry-mode]')
                    const source = group.querySelector('[data-tenant-managed-registry-source]')
                    if (source instanceof HTMLInputElement) {
                        source.required = enabled && mode?.value === 'image_pull_secret'
                    }
                }

                group.dataset.enabled = enabled ? 'true' : 'false'
                group.classList.toggle('opacity-70', !enabled)
                syncStatus(enabled)
            }

            toggle.addEventListener('change', sync)
            group.querySelector('[data-tenant-service-exposure-profile]')?.addEventListener('change', sync)
            group.querySelector('[data-tenant-managed-tls-mode]')?.addEventListener('change', sync)
            group.querySelector('[data-tenant-managed-registry-mode]')?.addEventListener('change', sync)
            sync()
        })
    }

    const initCapacityPolicyForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const policies = readJson('tenant-capacity-policy-state')
        const cluster = form.querySelector('[data-capacity-policy-cluster]')
        const fields = collectFields(form, 'data-capacity-policy-field')

        const applyPolicy = () => {
            const policy = policies[cluster?.value] || null
            for (const [name, input] of Object.entries(fields)) {
                const fallback = input.dataset.defaultValue ?? ''
                input.value = policy?.[name] ?? fallback
            }
        }

        cluster?.addEventListener('change', applyPolicy)
        applyPolicy()
    }

    const initAllocationChangeForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const namespaces = readJson('tenant-namespace-allocation-state')
        const advancedPreflight = readJson('tenant-namespace-allocation-advanced-preflight')
        const namespaceSelect = form.querySelector('[data-tenant-allocation-change-namespace]')
        const profileSelect = form.querySelector('[data-tenant-allocation-change-profile]')

        const currentProfile = form.querySelector('[data-tenant-allocation-profile="current"]')
        const proposedProfile = form.querySelector('[data-tenant-allocation-profile="proposed"]')
        // Native profile categories use the canonical accessible <details> disclosure.
        // No custom keyboard tab controller is needed.

        const contractValue = (contract, source, key) => {
            if (!contract) return null
            if (source === 'limits') {
                return key.split('.').reduce((value, part) => value?.[part], contract.limits) ?? null
            }
            return contract[source]?.[key] ?? null
        }

        const displayValue = (source, key, value) => {
            if (value === null || value === undefined || value === '') {
                const boundedQuotaKeys = [
                    'requests.cpu',
                    'limits.cpu',
                    'requests.memory',
                    'limits.memory',
                    'pods',
                    'requests.storage',
                    'persistentvolumeclaims',
                    'services',
                    'configmaps',
                    'secrets',
                ]
                return source === 'storage_policy' || (source === 'quota' && boundedQuotaKeys.includes(key))
                    ? 'Unbounded'
                    : 'Not declared'
            }
            return String(value)
        }

        const renderAdvancedComparison = (current, profile, namespaceId, profileId) => {
            const recorded = current?.advanced_evidence
            const recordedControls = recorded?.recorded ? recorded.controls || {} : {}
            const proposedControls =
                profileId === 'adopted_baseline' ? recordedControls : profile?.advanced_controls || {}
            const evaluated = advancedPreflight[namespaceId]?.[profileId] || {}
            let visible = 0

            form.querySelectorAll('[data-tenant-allocation-advanced-row]').forEach((row) => {
                const key = row.dataset.tenantAllocationAdvancedRow
                const currentControl = recordedControls[key]
                const proposedControl = evaluated[key]
                const requested = proposedControl?.requested || proposedControls[key]?.enabled === true
                const show = currentControl?.requested || requested
                row.hidden = !show
                if (!show) return
                visible += 1
                const currentCell = row.querySelector('[data-tenant-allocation-advanced-current]')
                const proposedCell = row.querySelector('[data-tenant-allocation-advanced-proposed]')
                const currentStatus = !recorded?.recorded
                    ? 'Not recorded'
                    : !currentControl?.requested
                      ? 'Not configured'
                      : currentControl.state === 'enabled'
                        ? 'Supported · Recorded'
                        : currentControl.state === 'unsupported'
                          ? 'Unavailable · Recorded'
                          : 'Configured · Recorded'
                const proposedStatus =
                    profileId === 'adopted_baseline'
                        ? 'Same as current · Not verified'
                        : !requested
                          ? 'Not configured'
                          : proposedControl?.state === 'enabled'
                            ? 'Supported · Preflight'
                            : proposedControl?.state === 'unsupported'
                              ? 'Unavailable · Preflight'
                              : 'Configured · Preflight pending'
                if (currentCell) {
                    currentCell.textContent = currentStatus
                    currentCell.title = currentControl?.reason || 'No verified provider execution evidence.'
                }
                if (proposedCell) {
                    proposedCell.textContent = proposedStatus
                    proposedCell.title = proposedControl?.reason || 'Provider execution not verified.'
                }
            })
            const empty = form.querySelector('[data-tenant-allocation-advanced-empty]')
            const list = form.querySelector('[data-tenant-allocation-advanced-list]')
            if (empty) empty.hidden = visible > 0
            if (list) list.hidden = visible === 0
        }

        // Classify only parseable Kubernetes quantities. Missing or unknown
        // quantities must not masquerade as capacity gains or approvals.
        const parsedQuantity = (raw) => {
            const match = /^(\d+(?:\.\d+)?)(m|Ki|Mi|Gi|Ti|Pi|Ei|k|K|M|G|T|P|E)?$/.exec(String(raw).trim())
            if (!match) return null
            const multipliers = {
                m: 0.001,
                k: 1e3,
                K: 1e3,
                M: 1e6,
                G: 1e9,
                T: 1e12,
                P: 1e15,
                E: 1e18,
                Ki: 2 ** 10,
                Mi: 2 ** 20,
                Gi: 2 ** 30,
                Ti: 2 ** 40,
                Pi: 2 ** 50,
                Ei: 2 ** 60,
            }
            const value = Number(match[1]) * (multipliers[match[2]] ?? 1)
            return Number.isFinite(value) ? value : null
        }

        const classifyChange = (before, after) => {
            const prior = before == null || before === '' ? null : String(before)
            const next = after == null || after === '' ? null : String(after)
            if (prior == null && next == null) return null
            if (prior == null) return 'Now defined'
            if (next == null) return 'No longer defined'
            const left = parsedQuantity(prior)
            const right = parsedQuantity(next)
            if (left != null && right != null) {
                if (left === right) return null
                return right > left ? 'Increased' : 'Reduced'
            }
            return prior === next ? null : 'Changed'
        }

        const highlightDimensions = [
            ['CPU Limits', 'quota', 'limits.cpu'],
            ['Memory Limits', 'quota', 'limits.memory'],
            ['Total Storage', 'quota', 'requests.storage'],
            ['CPU Requests', 'quota', 'requests.cpu'],
            ['Memory Requests', 'quota', 'requests.memory'],
            ['Pods', 'quota', 'pods'],
            ['Min PVC Size', 'storage_policy', 'min'],
            ['Max PVC Size', 'storage_policy', 'max'],
            ['PVCs', 'quota', 'persistentvolumeclaims'],
            ['Services', 'quota', 'services'],
            ['ConfigMaps', 'quota', 'configmaps'],
            ['Secrets', 'quota', 'secrets'],
            ['Default CPU Request', 'limits', 'default_request.cpu'],
            ['Default CPU Limit', 'limits', 'default.cpu'],
            ['Default Memory Request', 'limits', 'default_request.memory'],
            ['Default Memory Limit', 'limits', 'default.memory'],
        ]

        const renderContractPreview = (current, proposed) => {
            form.querySelectorAll('[data-tenant-allocation-metric-side]').forEach((cell) => {
                const selected = cell.dataset.tenantAllocationMetricSide === 'current' ? current : proposed
                const source = cell.dataset.tenantAllocationMetricSource
                const key = cell.dataset.tenantAllocationMetricKey
                cell.textContent = selected ? displayValue(source, key, contractValue(selected, source, key)) : '—'
            })
            form.querySelectorAll('[data-tenant-allocation-tech-current]').forEach((cell) => {
                const [source, ...parts] = cell.dataset.tenantAllocationTechCurrent.split('.')
                const key = parts.join('.')
                cell.textContent = current ? displayValue(source, key, contractValue(current, source, key)) : '—'
            })
            form.querySelectorAll('[data-tenant-allocation-tech-proposed]').forEach((cell) => {
                const [source, ...parts] = cell.dataset.tenantAllocationTechProposed.split('.')
                const key = parts.join('.')
                const beforeValue = contractValue(current, source, key)
                const afterValue = contractValue(proposed, source, key)
                const differs = !!current && !!proposed && classifyChange(beforeValue, afterValue) !== null
                cell.textContent = proposed ? displayValue(source, key, afterValue) : '—'
                cell.classList.toggle('text-kaori-primary', differs)
                cell.classList.toggle('text-content-primary', !differs)
            })

            const changed =
                current && proposed
                    ? highlightDimensions.flatMap(([label, source, key]) => {
                          const before = contractValue(current, source, key)
                          const after = contractValue(proposed, source, key)
                          return classifyChange(before, after) ? [{ label, source, key, before, after }] : []
                      })
                    : []

            const count = form.querySelector('[data-tenant-allocation-highlight-count]')
            if (count)
                count.textContent =
                    !current || !proposed
                        ? 'Choose contracts'
                        : changed.length === 0
                          ? 'No changes'
                          : `${changed.length} changes`

            const rows = Array.from(form.querySelectorAll('[data-tenant-allocation-highlight-item]'))
            rows.forEach((row, index) => {
                const diff = changed[index]
                row.hidden = !diff
                if (!diff) return
                const label = row.querySelector('[data-tenant-allocation-highlight-label]')
                const from = row.querySelector('[data-tenant-allocation-highlight-from]')
                const to = row.querySelector('[data-tenant-allocation-highlight-to]')
                if (label) label.textContent = diff.label
                if (from) from.textContent = displayValue(diff.source, diff.key, diff.before)
                if (to) to.textContent = displayValue(diff.source, diff.key, diff.after)
            })
            const more = form.querySelector('[data-tenant-allocation-highlight-more]')
            if (more) {
                const extra = Math.max(0, changed.length - rows.length)
                more.hidden = extra === 0
                more.textContent = extra ? `+ ${extra} additional changes in the selected contract` : ''
            }
        }

        const renderAllocationChange = ({ preferCurrentProfile = false } = {}) => {
            const current = namespaces[namespaceSelect?.value] || null

            if (preferCurrentProfile && current && profileSelect) {
                if (current.profile_id && profileSelect.querySelector(`option[value="${current.profile_id}"]`)) {
                    profileSelect.value = String(current.profile_id)
                } else if (profileSelect.querySelector('option[value="adopted_baseline"]')) {
                    profileSelect.value = 'adopted_baseline'
                }
            }

            const proposed =
                profileSelect?.value === 'adopted_baseline' ? current : profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'

            if (currentProfile) {
                currentProfile.textContent = current
                    ? `${current.profile_name} · v${current.profile_version || '—'}`
                    : '—'
            }
            if (proposedProfile) proposedProfile.textContent = proposed ? proposedLabel : '—'
            renderContractPreview(current, proposed)
            renderAdvancedComparison(current, proposed, namespaceSelect?.value, profileSelect?.value)
        }

        namespaceSelect?.addEventListener('change', () => renderAllocationChange({ preferCurrentProfile: true }))
        profileSelect?.addEventListener('change', () => renderAllocationChange())
        renderAllocationChange({ preferCurrentProfile: true })
    }

    // Present Capsule authoritative quota evidence; do not infer eligibility,
    // capacity approval or Native ResourceQuota ownership from this diff.
    const renderCapsuleQuotaPreview = (form, current, proposed) => {
        const dimensions = [
            ['requests.cpu', 'CPU Requests'],
            ['limits.cpu', 'CPU Limits'],
            ['requests.memory', 'Memory Requests'],
            ['limits.memory', 'Memory Limits'],
            ['pods', 'Pods'],
            ['requests.storage', 'Total Storage'],
            ['persistentvolumeclaims', 'PVCs'],
            ['services', 'Services'],
            ['configmaps', 'ConfigMaps'],
            ['secrets', 'Secrets'],
        ]
        // GlobalResourceQuota cutover still exposes the six headline metrics;
        // the two Tenant CR forms disclose all ten supported quota dimensions.
        // Both admitted Capsule quota sources can govern all ten supported
        // ResourceQuota hard dimensions. Every one is now visible in the same
        // provider-authoritative disclosure before a provider write.
        const comparisonDimensions = dimensions
        const countDimensions = new Set(['pods', 'persistentvolumeclaims', 'services', 'configmaps', 'secrets'])
        const factors = {
            '': 1,
            m: 0.001,
            k: 1000,
            M: 1000000,
            G: 1000000000,
            T: 1000000000000,
            Ki: 1024,
            Mi: 1024 ** 2,
            Gi: 1024 ** 3,
            Ti: 1024 ** 4,
            Pi: 1024 ** 5,
        }
        const formatted = (quota, key) => {
            const raw = quota?.[key]
            return raw === null || raw === undefined || raw === '' ? 'Unbounded' : String(raw)
        }
        const numericQuantity = (key, value) => {
            const match = /^([0-9]+(?:\.[0-9]+)?|\.[0-9]+)(m|k|M|G|T|Ki|Mi|Gi|Ti|Pi)?$/.exec(value.trim())
            if (!match) return null
            const suffix = match[2] || ''
            if (countDimensions.has(key) && suffix) return null
            const result = Number(match[1]) * factors[suffix]
            return Number.isFinite(result) ? result : null
        }
        const equivalent = (key, left, right) => {
            const a = formatted(left, key)
            const b = formatted(right, key)
            if (a === b) return true
            if (a === 'Unbounded' || b === 'Unbounded') return false
            const aNumber = numericQuantity(key, a)
            const bNumber = numericQuantity(key, b)
            return (
                aNumber !== null &&
                bNumber !== null &&
                Math.abs(aNumber - bNumber) <= Number.EPSILON * Math.max(1, Math.abs(aNumber), Math.abs(bNumber))
            )
        }
        form.querySelectorAll('[data-tenant-quota-metric-side]').forEach((cell) => {
            const source = cell.dataset.tenantQuotaMetricSide === 'current' ? current : proposed
            const present = cell.dataset.tenantQuotaMetricSide === 'current' ? current !== null : proposed !== null
            cell.textContent = present ? formatted(source, cell.dataset.tenantQuotaMetricKey) : '—'
        })
        const summary = form.querySelector('[data-tenant-quota-change-summary]')
        const highlights = form.querySelector('[data-tenant-quota-change-detail]')
        if (current === null || proposed === null) {
            if (summary) summary.textContent = 'Choose contracts'
            if (highlights) {
                highlights.hidden = true
                highlights.textContent = ''
            }
            return
        }
        const changed = comparisonDimensions.filter(([key]) => !equivalent(key, current, proposed))
        if (summary) {
            summary.textContent =
                changed.length === 0
                    ? 'No quota differences'
                    : `${changed.length} of ${comparisonDimensions.length} quota dimensions differ · Read only`
        }
        if (highlights) {
            highlights.hidden = changed.length === 0
            highlights.textContent = changed.length
                ? changed
                      .slice(0, 3)
                      .map(([key, label]) => `${label}: ${formatted(current, key)} → ${formatted(proposed, key)}`)
                      .join(' · ') + (changed.length > 3 ? ` · +${changed.length - 3} more` : '')
                : ''
        }
    }

        const renderCapsuleProfileCoverage = (form, profile, tenantId, profileId) => {
        const valueFor = (source, key) => {
            if (!profile) return null
            const object = profile[source] || {}
            if (source === 'limits') return key.split('.').reduce((value, part) => value?.[part], object) ?? null
            return object[key] ?? null
        }
        form.querySelectorAll('[data-tenant-capsule-external-source]').forEach((cell) => {
            const source = cell.dataset.tenantCapsuleExternalSource
            const key = cell.dataset.tenantCapsuleExternalKey
            const value = valueFor(source, key)
            cell.textContent = !profile ? '—' : value === null || value === '' ? 'Not configured' : `Not governed · ${value}`
        })
        const advanced = profile?.advanced_controls || {}
        const committedEvaluations = readJson('tenant-capsule-advanced-profile-preflight')
        const evaluation = committedEvaluations?.[tenantId]?.[profileId] || {}
        const requestedUnsupported = []
        form.querySelectorAll('[data-tenant-capsule-advanced-preview]').forEach((cell) => {
            const key = cell.dataset.tenantCapsuleAdvancedPreview
            const control = advanced[key]
            const requested = control === true || (control && typeof control === 'object' && control.enabled !== false)
            const preflight = evaluation[key]
            if (!profile) {
                cell.textContent = '—'
            } else if (!requested) {
                cell.textContent = 'Not requested'
            } else if (preflight?.state === 'enabled' && preflight.requested === true) {
                cell.textContent = 'Available · Capability preflight'
            } else {
                const reason = preflight?.reason || 'Committed provider capability evidence unavailable.'
                cell.textContent = `Unavailable · ${reason}`
                requestedUnsupported.push(preflight?.label || key)
            }
        })
        if (profile) {
            // Match server resource_profile_base_control_state() exactly:
            // any configured mapping (not only truthy leaf values) is an
            // unsupported managed control on a Capsule quota-only path.
            if (Object.keys(profile.storage_policy || {}).length > 0) {
                requestedUnsupported.push('Per-PVC Policy')
            }
            if (Object.keys(profile.limits || {}).length > 0) {
                requestedUnsupported.push('Container Defaults')
            }
        }
        const alert = form.querySelector('[data-tenant-capsule-coverage-alert]')
        if (alert) {
            alert.hidden = requestedUnsupported.length === 0
            alert.textContent = requestedUnsupported.length
                ? `Unsupported by this Capsule quota authority: ${requestedUnsupported.join(', ')}. Disable these Managed controls in a compatible Resource Profile before applying.`
                : ''
        }
        const apply = form.querySelector('[data-tenant-capsule-apply-button]')
        if (apply) {
            // Preserve server-rendered role/capability gates; never re-enable
            // an action that was disabled by server authorization.
            if (!Object.hasOwn(apply.dataset, 'kaoriInitiallyDisabled')) {
                apply.dataset.kaoriInitiallyDisabled = String(apply.disabled)
            }
            const blocked = apply.dataset.kaoriInitiallyDisabled === 'true' || !profile || requestedUnsupported.length > 0
            apply.disabled = blocked
            apply.setAttribute('aria-disabled', String(blocked))
        }
    }

    const initSharedAllocationForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const tenants = readJson('tenant-capsule-shared-allocation-state')
        const tenantSelect = form.querySelector('[data-tenant-shared-allocation-tenant]')
        const profileSelect = form.querySelector('[data-tenant-shared-allocation-profile]')

        const currentSource = form.querySelector('[data-tenant-shared-current-source]')
        const currentCpu = form.querySelector('[data-tenant-shared-current-cpu]')
        const currentMemory = form.querySelector('[data-tenant-shared-current-memory]')
        const proposedProfile = form.querySelector('[data-tenant-shared-proposed-profile]')
        const proposedCpu = form.querySelector('[data-tenant-shared-proposed-cpu]')
        const proposedMemory = form.querySelector('[data-tenant-shared-proposed-memory]')

        const requestValue = (quota, resource) => quota?.[`requests.${resource}`] || 'Unbounded'

        const render = () => {
            const current = tenants[tenantSelect?.value] || null
            const proposed = profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'
            const source = current?.source || {}

            if (currentSource) {
                currentSource.textContent = current
                    ? `GlobalResourceQuota/${source.name || 'unknown'} · ${current.provider_api_version || 'unknown'}`
                    : '—'
            }
            if (currentCpu) currentCpu.textContent = current ? requestValue(current.current_quota, 'cpu') : '—'
            if (currentMemory) currentMemory.textContent = current ? requestValue(current.current_quota, 'memory') : '—'
            if (proposedProfile) proposedProfile.textContent = proposed ? proposedLabel : '—'
            if (proposedCpu) proposedCpu.textContent = proposed ? requestValue(proposed.quota, 'cpu') : '—'
            if (proposedMemory) proposedMemory.textContent = proposed ? requestValue(proposed.quota, 'memory') : '—'
            renderCapsuleQuotaPreview(
                form,
                current ? current.current_quota || {} : null,
                proposed ? proposed.quota || {} : null
            )
            renderCapsuleProfileCoverage(form, proposed, tenantSelect?.value, profileSelect?.value)
        }

        tenantSelect?.addEventListener('change', render)
        profileSelect?.addEventListener('change', render)
        render()
    }

    const quotaSummary = (quota) => {
        if (!quota) return '—'
        const parts = [
            ['CPU requests', quota['requests.cpu']],
            ['CPU limits', quota['limits.cpu']],
            ['Memory requests', quota['requests.memory']],
            ['Memory limits', quota['limits.memory']],
            ['Pods', quota.pods],
            ['Storage', quota['requests.storage']],
        ]
            .filter(([, value]) => value !== undefined && value !== null && String(value) !== '')
            .map(([label, value]) => `${label} ${value}`)
        return parts.length ? parts.join(' · ') : 'No bounded supported dimensions'
    }

    const initTenantQuotaCutoverForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const tenants = readJson('tenant-capsule-tenant-quota-state')
        const tenantSelect = form.querySelector('[data-tenant-quota-tenant]')
        const profileSelect = form.querySelector('[data-tenant-quota-profile]')
        const currentSource = form.querySelector('[data-tenant-quota-current-source]')
        const currentScope = form.querySelector('[data-tenant-quota-current-scope]')
        const proposedProfile = form.querySelector('[data-tenant-quota-proposed-profile]')
        const proposedSummary = form.querySelector('[data-tenant-quota-proposed-summary]')

        const render = () => {
            const current = tenants[tenantSelect?.value] || null
            const proposed = profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'
            const source = current?.source || {}
            if (currentSource) {
                currentSource.textContent = current
                    ? `Tenant/${source.name || 'unknown'} · ${source.api_version || 'unknown'}`
                    : '—'
            }
            if (currentScope) {
                currentScope.textContent = current
                    ? `Scope ${current.scope || 'Tenant'} · ${quotaSummary(current.current_quota)}`
                    : '—'
            }
            if (proposedProfile) proposedProfile.textContent = proposed ? proposedLabel : '—'
            if (proposedSummary) proposedSummary.textContent = proposed ? quotaSummary(proposed.quota) : '—'
            renderCapsuleQuotaPreview(
                form,
                current ? current.current_quota || {} : null,
                proposed ? proposed.quota || {} : null
            )
            renderCapsuleProfileCoverage(form, proposed, tenantSelect?.value, profileSelect?.value)
        }

        tenantSelect?.addEventListener('change', render)
        profileSelect?.addEventListener('change', render)
        render()
    }

    const initTenantQuotaManagedForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const governance = readJson('tenant-capsule-tenant-quota-governance')
        const tenantSelect = form.querySelector('[data-tenant-quota-managed-tenant]')
        const profileSelect = form.querySelector('[data-tenant-quota-managed-profile]')
        const current = form.querySelector('[data-tenant-quota-managed-current]')
        const summary = form.querySelector('[data-tenant-quota-managed-summary]')
        const proposedSummary = form.querySelector('[data-tenant-quota-managed-proposed-summary]')

        const render = () => {
            const state = governance[tenantSelect?.value] || null
            const proposed = profiles[profileSelect?.value] || null
            const proposedLabel = profileSelect?.selectedOptions?.[0]?.textContent?.trim() || '—'
            if (current) {
                current.textContent = state
                    ? `${state.scope || 'Tenant'} · ${state.provenance || 'kaori_managed'}`
                    : '—'
            }
            const nextProfile = form.querySelector('[data-tenant-quota-managed-proposed-profile]')
            if (nextProfile) nextProfile.textContent = proposed ? proposedLabel : '—'
            if (summary) summary.textContent = state ? quotaSummary(state.desired_quota) : '—'
            if (proposedSummary) proposedSummary.textContent = proposed ? quotaSummary(proposed.quota) : '—'
            renderCapsuleQuotaPreview(
                form,
                state ? state.desired_quota || {} : null,
                proposed ? proposed.quota || {} : null
            )
            renderCapsuleProfileCoverage(form, proposed, tenantSelect?.value, profileSelect?.value)
        }

        tenantSelect?.addEventListener('change', render)
        profileSelect?.addEventListener('change', render)
        render()
    }

    const advancedControlSummary = (key, value) => {
        if (!value || value === true || typeof value !== 'object') return ''
        const yesNo = (flag) => (flag ? 'Allow' : 'Deny')

        if (key === 'ingress') {
            return value.enforcement_required === false ? 'Preflight only' : 'Enforcement required'
        }
        if (key === 'service_exposure') {
            if (value.profile_key === 'ingress_only') return 'Ingress only'
            return [
                `ClusterIP ${yesNo(value.allow_cluster_ip)}`,
                `Ingress ${yesNo(value.allow_ingress)}`,
                `NodePort ${yesNo(value.allow_node_port)}`,
                `LoadBalancer ${yesNo(value.allow_load_balancer)}`,
                `ExternalName ${yesNo(value.allow_external_name)}`,
            ].join(' · ')
        }
        if (key === 'hostname_reservation') {
            return [value.match_mode, value.hostname_pattern].filter(Boolean).join(' · ')
        }
        if (key === 'managed_tls' || key === 'managed_registry') {
            return [String(value.mode || '').replaceAll('_', ' '), value.resource_name, value.source_reference]
                .filter(Boolean)
                .join(' · ')
        }
        if (key === 'capsule_namespace_controls') {
            const optionCount =
                value.namespace_options && typeof value.namespace_options === 'object'
                    ? Object.keys(value.namespace_options).length
                    : 0
            return `Tenant prefix ${value.force_tenant_prefix ? 'On' : 'Off'} · ${optionCount} namespace option${optionCount === 1 ? '' : 's'}`
        }
        if (key === 'capsule_resource_rules') {
            const registries = Array.isArray(value.container_registries) ? value.container_registries.length : 0
            const priority = Array.isArray(value.priority_classes) ? value.priority_classes.length : 0
            const storage = Array.isArray(value.storage_classes) ? value.storage_classes.length : 0
            return `${registries} registries · ${priority} priority classes · ${storage} storage classes`
        }
        if (key === 'capsule_resource_pools' || key === 'capsule_replication') {
            return [String(value.resource_kind || '').replaceAll('_', ' '), value.resource_name]
                .filter(Boolean)
                .join(' · ')
        }
        if (key === 'capsule_tenant_cordon') {
            return `Cordon ${value.cordoned ? 'On' : 'Off'} · Prevent deletion ${value.prevent_deletion ? 'On' : 'Off'}`
        }
        return ''
    }

    const initNamespaceForm = (form) => {
        if (!(form instanceof HTMLFormElement) || form.dataset.kaoriInitialized === 'true') return
        form.dataset.kaoriInitialized = 'true'

        const profiles = readJson('tenant-namespace-allocation-profiles')
        const environments = readJson('tenant-environment-advanced-control-state')
        const profileSelect = form.querySelector('[data-tenant-namespace-profile]')
        const environmentSelect = form.querySelector('[data-tenant-namespace-environment]')
        const providerLabel = form.querySelector('[data-tenant-namespace-provider-label]')
        const fields = collectFields(form, 'data-tenant-namespace-resource-field')
        setReadonly(form, fields, true)

        const renderAdvancedControls = () => {
            const profile = profiles[profileSelect?.value] || null
            const environment = environments[environmentSelect?.value] || null
            const requested = profile?.advanced_controls || {}
            const placementControls = environment?.controls || {}

            if (providerLabel) {
                if (!environment) {
                    providerLabel.textContent = 'No placement selected'
                } else {
                    const provider = environment.provider_key === 'capsule' ? 'Capsule' : 'Native Kubernetes'
                    const state = String(environment.provider_state || '').replaceAll('_', ' ')
                    providerLabel.textContent = state ? `${provider} · ${state}` : provider
                }
            }

            form.querySelectorAll('[data-tenant-namespace-advanced-control]').forEach((card) => {
                const key = card.getAttribute('data-tenant-namespace-advanced-control')
                const toggle = card.querySelector('[data-tenant-namespace-advanced-toggle]')
                const stateLabel = card.querySelector('[data-tenant-namespace-advanced-state]')
                const reason = card.querySelector('[data-tenant-namespace-advanced-reason]')
                const rawRequest = requested[key]
                const isRequested =
                    rawRequest === true ||
                    (rawRequest && typeof rawRequest === 'object' && rawRequest.enabled !== false)
                const placement = placementControls[key] || null
                const configuration = advancedControlSummary(key, rawRequest)
                const isAvailable = isRequested && placement?.state === 'enabled'

                if (toggle) toggle.checked = isRequested
                card.dataset.requested = isRequested ? 'true' : 'false'
                card.dataset.available = isAvailable ? 'true' : 'false'
                card.classList.toggle('opacity-60', isRequested && !isAvailable)

                if (!isRequested) {
                    if (stateLabel) stateLabel.textContent = 'Off'
                    if (reason) reason.textContent = 'Not enabled in the selected Resource Profile.'
                    return
                }

                if (!environment) {
                    if (stateLabel) stateLabel.textContent = 'Select placement'
                    if (reason) {
                        reason.textContent = configuration
                            ? `${configuration}. Choose a Tenant Environment to evaluate provider support.`
                            : 'Choose a Tenant Environment to evaluate provider support.'
                    }
                    return
                }

                if (isAvailable) {
                    if (stateLabel) stateLabel.textContent = 'Enabled'
                    if (reason) {
                        reason.textContent = configuration
                            ? `${configuration}. Supported by the selected provider.`
                            : 'Requested by profile and supported by the selected provider.'
                    }
                    return
                }

                if (stateLabel) stateLabel.textContent = 'Unavailable'
                if (reason) {
                    const unavailableReason = placement?.reason || 'The selected provider cannot enforce this control.'
                    reason.textContent = configuration ? `${configuration}. ${unavailableReason}` : unavailableReason
                }
            })
        }

        const applyNamespaceProfile = () => {
            const profile = profiles[profileSelect?.value] || null
            applyValues(fields, profile)
            // Values without a managed Resource Profile dimension should not
            // render as an unexplained blank quota cell after selection.
            form.querySelectorAll('[data-tenant-quota-default-card] [data-tenant-value-display]').forEach((cell) => {
                if (cell.textContent.trim() === '—' && profile) cell.textContent = 'Not managed'
            })
            renderAdvancedControls()
        }

        profileSelect?.addEventListener('change', applyNamespaceProfile)
        environmentSelect?.addEventListener('change', renderAdvancedControls)
        applyNamespaceProfile()
    }

    const initProfileRolloutForm = (form) => {
        if (!(form instanceof HTMLFormElement)) return
        const select = form.querySelector('[data-tenant-profile-rollout-select]')
        const submit = form.querySelector('[data-tenant-profile-rollout-submit]')
        const status = form.parentElement?.querySelector('[data-tenant-profile-rollout-status]')
        const currentBadge = status?.querySelector('[data-rollout-already-current]')
        const pendingBadge = status?.querySelector('[data-rollout-needs-change]')
        const message = status?.querySelector('[data-rollout-status-message]')
        if (!(select instanceof HTMLSelectElement) || !(submit instanceof HTMLButtonElement)) return

        const sync = () => {
            const option = select.selectedOptions[0]
            const selected = Boolean(option?.value)
            const eligible = selected && option?.dataset.rolloutEligible === 'true'
            const current = eligible && option?.dataset.rolloutCurrent === 'true'
            const permitted = form.dataset.rolloutPermitted === 'true'
            const disabled = !permitted || !eligible || current

            submit.disabled = disabled
            submit.setAttribute('aria-disabled', disabled ? 'true' : 'false')
            if (currentBadge) currentBadge.hidden = !current
            if (pendingBadge) pendingBadge.hidden = !eligible || current
            if (message) {
                message.textContent = !permitted
                    ? 'Rollout is unavailable for this profile or permission scope.'
                    : !selected
                      ? 'Select a Tenant to check committed allocation readiness.'
                      : !eligible
                        ? 'This Tenant cannot use Native Resource Profile rollout.'
                        : current
                          ? 'All attached Namespace committed versions, quotas, defaults, and storage policies match. Provider drift is checked separately.'
                          : `${option.dataset.rolloutPending} Namespace(s) require rollout; capacity admission and provider verification still apply.`
            }
        }

        if (form.dataset.kaoriRolloutInitialized !== 'true') {
            form.dataset.kaoriRolloutInitialized = 'true'
            select.addEventListener('change', sync)
            form.addEventListener('submit', (event) => {
                sync()
                if (submit.disabled) event.preventDefault()
            })
        }
        sync()
    }

    const init = (root = document) => {
        const scope = root instanceof Element || root instanceof Document ? root : document
        scope.querySelectorAll('[data-tenant-resource-profile-form]').forEach(initProfileForm)
        scope.querySelectorAll('[data-tenant-profile-rollout-form]').forEach(initProfileRolloutForm)
        scope.querySelectorAll('[data-tenant-advanced-controls]').forEach(initAdvancedControls)
        scope.querySelectorAll('[data-tenant-capacity-policy-form]').forEach(initCapacityPolicyForm)
        scope.querySelectorAll('[data-tenant-allocation-change-form]').forEach(initAllocationChangeForm)
        scope.querySelectorAll('[data-tenant-shared-allocation-form]').forEach(initSharedAllocationForm)
        scope.querySelectorAll('[data-tenant-quota-allocation-form]').forEach(initTenantQuotaCutoverForm)
        scope.querySelectorAll('[data-tenant-quota-managed-form]').forEach(initTenantQuotaManagedForm)
        scope.querySelectorAll('[data-tenant-namespace-allocation-form]').forEach(initNamespaceForm)
    }

    document.addEventListener('htmx:afterSwap', (event) => init(event.target))
    window.addEventListener('pageshow', () => init())
    init()
})()
