(() => {
  const formSelector = '[data-configmap-editor-form]';

  const updateConfigMapName = (form, namespaceValue) => {
    const field = form.querySelector('#configmap-name');
    if (!(field instanceof HTMLInputElement)) return;
    const enabled = Boolean(namespaceValue);
    field.disabled = !enabled;
    field.placeholder = enabled ? 'application-config' : 'Select namespace first';
    if (!enabled) field.value = '';
  };

  const invalidateForm = (form) => {
    form.dispatchEvent(new Event('input', { bubbles: true }));
  };

  const toggleReplaceConfirmation = (form) => {
    const mode = form.querySelector('[data-configmap-update-mode]');
    const confirmation = form.querySelector('[data-configmap-replace-confirmation]');
    if (!(mode instanceof HTMLSelectElement) || !(confirmation instanceof HTMLElement)) return;

    const replace = mode.value === 'replace';
    confirmation.hidden = !replace;
    confirmation.setAttribute('aria-hidden', replace ? 'false' : 'true');
    if (!replace) {
      const checkbox = confirmation.querySelector('input[type="checkbox"]');
      if (checkbox instanceof HTMLInputElement) checkbox.checked = false;
    }
  };

  const resetValidationPreview = (form) => {
    const preview = form.querySelector('[data-configmap-validation-preview]');
    const template = document.getElementById('configmap-validation-pending-template');
    if (!(preview instanceof HTMLElement) || !(template instanceof HTMLTemplateElement)) return;

    preview.replaceChildren(template.content.cloneNode(true));
    preview.dataset.validationStatus = 'pending';
    preview.className =
      'rounded-xl border border-outline-default bg-surface-card p-4 sm:p-5';
    window.renderKaoriIcons?.();
  };

  const initialise = (root = document) => {
    if (root.matches?.(formSelector)) toggleReplaceConfirmation(root);
    root.querySelectorAll?.(formSelector).forEach(toggleReplaceConfirmation);
  };

  document.addEventListener('change', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const form = target.closest(formSelector);
    if (!(form instanceof HTMLFormElement)) return;

    if (target.matches('[data-configmap-cluster]')) updateConfigMapName(form, '');
    if (target.matches('[data-configmap-namespace]')) updateConfigMapName(form, target.value);
    if (target.matches('[data-configmap-update-mode]')) toggleReplaceConfirmation(form);
  });

  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const form = target.closest(formSelector);
    if (!(form instanceof HTMLFormElement)) return;

    const addButton = target.closest('[data-add-entry]');
    if (addButton) {
      const list = form.querySelector('#configmap-entries');
      const template = form.querySelector('#configmap-entry-template');
      if (list && template instanceof HTMLTemplateElement) {
        const fragment = template.content.cloneNode(true);
        list.append(fragment);
        const entries = list.querySelectorAll('.configmap-entry');
        entries[entries.length - 1]?.querySelector('input[name="entry_key"]')?.focus();
        window.renderKaoriIcons?.();
        invalidateForm(form);
      }
      return;
    }

    const removeButton = target.closest('[data-remove-entry]');
    if (!removeButton) return;
    const list = form.querySelector('#configmap-entries');
    const entry = removeButton.closest('.configmap-entry');
    if (!list || !entry) return;

    if (list.querySelectorAll('.configmap-entry').length > 1) {
      entry.remove();
    } else {
      entry.querySelectorAll('input, textarea').forEach((field) => {
        field.value = '';
      });
      const kind = entry.querySelector('select[name="entry_kind"]');
      if (kind instanceof HTMLSelectElement) kind.value = 'text';
    }
    invalidateForm(form);
  });

  document.addEventListener('kaori:operation-validation-invalidated', (event) => {
    const formId = event.detail?.formId;
    const form = formId ? document.getElementById(formId) : null;
    if (form instanceof HTMLFormElement && form.matches(formSelector)) {
      resetValidationPreview(form);
    }
  });

  document.addEventListener('htmx:load', (event) => initialise(event.detail?.elt || document));
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initialise());
  } else {
    initialise();
  }
})();
