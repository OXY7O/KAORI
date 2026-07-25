(() => {
  const selector = 'form[data-validation-gated]';

  const setValidated = (form, validated) => {
    if (!form) return;
    form.dataset.validationState = validated ? 'validated' : 'pending';
    form.querySelectorAll('[data-validation-apply]').forEach((button) => {
      button.disabled = !validated;
      button.setAttribute('aria-disabled', validated ? 'false' : 'true');
    });
  };

  const invalidate = (event) => {
    const form = event.target.closest(selector);
    if (form && !event.target.matches('[name="operation"]')) setValidated(form, false);
  };

  document.addEventListener('input', invalidate);
  document.addEventListener('change', invalidate);
  document.addEventListener('kaori:operation-validated', (event) => {
    const formId = event.detail && event.detail.formId;
    if (formId) setValidated(document.getElementById(formId), true);
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll(selector).forEach((form) => setValidated(form, false));
  });
})();
