(() => {
  const formSelector = 'form[data-validation-gated]';
  const applySelector = '[data-validation-apply]';
  const validatedEventName = 'kaori:operation-validated';

  const applyButtonsFor = (form) => {
    if (!form) return [];
    const buttons = Array.from(form.querySelectorAll(applySelector));
    if (!form.id) return buttons;

    document.querySelectorAll(`${applySelector}[data-validation-form="${form.id}"]`).forEach((button) => {
      if (!buttons.includes(button)) buttons.push(button);
    });
    return buttons;
  };

  const resolveFormId = (detail) => {
    if (!detail || typeof detail !== 'object') return '';
    return (
      detail.formId ||
      (detail.value && detail.value.formId) ||
      (detail.detail && detail.detail.formId) ||
      ''
    );
  };

  const setValidated = (form, validated) => {
    if (!form) return;

    form.dataset.validationState = validated ? 'validated' : 'pending';
    applyButtonsFor(form).forEach((button) => {
      if (!button.dataset.validationPendingTitle) {
        button.dataset.validationPendingTitle =
          button.getAttribute('title') ||
          'Run validation after the latest input change before applying this operation';
      }

      button.disabled = !validated;
      button.setAttribute('aria-disabled', validated ? 'false' : 'true');
      button.setAttribute(
        'title',
        validated
          ? 'Validation passed. This operation is ready to apply.'
          : button.dataset.validationPendingTitle,
      );
    });
  };

  const initialiseForms = (root = document) => {
    if (root.matches && root.matches(formSelector)) setValidated(root, false);
    if (!root.querySelectorAll) return;
    root.querySelectorAll(formSelector).forEach((form) => {
      if (form.dataset.validationState !== 'validated') setValidated(form, false);
    });
  };

  const invalidate = (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const associatedForm = target.form instanceof HTMLFormElement ? target.form : null;
    const explicitFormId = target.getAttribute('form');
    const form =
      target.closest(formSelector) ||
      (associatedForm && associatedForm.matches(formSelector) ? associatedForm : null) ||
      (explicitFormId ? document.getElementById(explicitFormId) : null);
    if (form && form.matches(formSelector) && !target.matches('[name="operation"]')) {
      const wasValidated = form.dataset.validationState === 'validated';
      setValidated(form, false);
      if (wasValidated) {
        form.dispatchEvent(
          new CustomEvent('kaori:operation-validation-invalidated', {
            bubbles: true,
            detail: { formId: form.id || '' },
          }),
        );
      }
    }
  };

  const handleValidatedEvent = (event) => {
    const formId = resolveFormId(event.detail);
    if (formId) setValidated(document.getElementById(formId), true);
  };

  const handleAfterRequest = (event) => {
    const xhr = event.detail && event.detail.xhr;
    if (!xhr || typeof xhr.getResponseHeader !== 'function') return;

    const triggerHeader = xhr.getResponseHeader('HX-Trigger');
    if (!triggerHeader) return;

    try {
      const triggers = JSON.parse(triggerHeader);
      const formId = resolveFormId(triggers[validatedEventName]);
      if (formId) setValidated(document.getElementById(formId), true);
    } catch (_error) {
      // Ignore malformed or non-JSON trigger headers; HTMX will handle its own events.
    }
  };

  document.addEventListener('input', invalidate);
  document.addEventListener('change', invalidate);
  document.addEventListener(validatedEventName, handleValidatedEvent);
  document.addEventListener('htmx:afterRequest', handleAfterRequest);
  document.addEventListener('htmx:load', (event) => initialiseForms(event.detail && event.detail.elt));

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initialiseForms());
  } else {
    initialiseForms();
  }
})();
