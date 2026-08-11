(() => {
  const parseConfig = (value, fallback = {}) => {
    if (!value) return fallback;
    try {
      return JSON.parse(value);
    } catch (_error) {
      return fallback;
    }
  };

  const getWorkspace = () => document.querySelector('[data-report-schedules-page]');

  const initScheduleForms = () => {
    const workspace = getWorkspace();
    if (!workspace) return;

    const defaults = parseConfig(workspace.dataset.scheduleDefaultSections);
    const allowedFormats = parseConfig(workspace.dataset.scheduleAllowedFormats);
    const familyByType = parseConfig(workspace.dataset.scheduleFamilyByType);

    workspace.querySelectorAll('[data-schedule-form]').forEach((form) => {
      if (form.dataset.initialized === 'true') return;
      form.dataset.initialized = 'true';

      const reportType = form.querySelector('[data-schedule-report-type]');
      const outputFormat = form.querySelector('[data-schedule-output-format]');
      const period = form.querySelector('[data-schedule-period]');
      const cadence = form.querySelector('[data-schedule-cadence]');
      const weeklyField = form.querySelector('[data-schedule-weekly-field]');
      const monthlyField = form.querySelector('[data-schedule-monthly-field]');
      const sectionError = form.querySelector('[data-schedule-section-error]');

      const syncTiming = () => {
        const value = cadence?.value || 'weekly';
        weeklyField?.classList.toggle('hidden', value !== 'weekly');
        monthlyField?.classList.toggle('hidden', value !== 'monthly');
      };

      const syncContract = (resetSections = false) => {
        const selectedType = reportType?.value || '';
        const formats = allowedFormats[selectedType] || [];
        const family = familyByType[selectedType] || 'analytics';

        Array.from(outputFormat?.options || []).forEach((option) => {
          option.hidden = !formats.includes(option.value);
          option.disabled = !formats.includes(option.value);
        });
        if (outputFormat && !formats.includes(outputFormat.value)) {
          outputFormat.value = formats[0] || '';
        }

        Array.from(period?.options || []).forEach((option) => {
          const allowed = family === 'inventory' ? option.value === 'snapshot' : option.value !== 'snapshot';
          option.hidden = !allowed;
          option.disabled = !allowed;
        });
        if (period) {
          if (family === 'inventory') period.value = 'snapshot';
          else if (period.value === 'snapshot') period.value = '30d';
        }

        form.querySelectorAll('[data-schedule-section-group]').forEach((group) => {
          const active = group.dataset.scheduleSectionGroup === selectedType;
          group.classList.toggle('hidden', !active);
          group.querySelectorAll('input[name="sections"]').forEach((input) => {
            input.disabled = !active;
            if (resetSections && active && input.type === 'checkbox') {
              input.checked = (defaults[selectedType] || []).includes(input.value);
            }
          });
        });
        sectionError?.classList.add('hidden');
      };

      reportType?.addEventListener('change', () => syncContract(true));
      cadence?.addEventListener('change', syncTiming);
      form
        .querySelectorAll('[data-schedule-reset-sections]')
        .forEach((button) => button.addEventListener('click', () => syncContract(true)));
      form.addEventListener('submit', (event) => {
        syncContract(false);
        const activeGroup = form.querySelector(`[data-schedule-section-group="${reportType?.value || ''}"]`);
        if (
          activeGroup?.dataset.scheduleFamily !== 'inventory' &&
          !activeGroup?.querySelector('input[type="checkbox"]:checked')
        ) {
          event.preventDefault();
          sectionError?.classList.remove('hidden');
        }
      });

      syncContract(false);
      syncTiming();
    });

    if (workspace.dataset.scheduleOpenDialog === 'true') {
      const dialog = document.getElementById('schedule-form-dialog');
      if (dialog && !dialog.open && typeof dialog.showModal === 'function') dialog.showModal();
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScheduleForms, { once: true });
  } else {
    initScheduleForms();
  }

  document.body.addEventListener('htmx:afterSwap', (event) => {
    initScheduleForms();
    if (window.lucide && event.detail?.target?.id === 'schedule-registry') window.lucide.createIcons();
  });
})();
