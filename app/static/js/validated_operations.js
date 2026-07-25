(() => {
  const formSelector = 'form[data-validation-gated]';
  const applySelector = '[data-validation-apply]';
  const validatedEventName = 'kaori:operation-validated';

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
    form.querySelectorAll(applySelector).forEach((button) => {
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

    const form = target.closest(formSelector);
    if (form && !target.matches('[name="operation"]')) setValidated(form, false);
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
