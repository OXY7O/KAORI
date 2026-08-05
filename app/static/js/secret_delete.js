(() => {
  const formSelector = '#delete-secret-form';

  const invalidateDeleteValidation = (form) => {
    if (!(form instanceof HTMLFormElement)) return;
    form.querySelector('[data-secret-delete-validation-token]')?.remove();
    const finalAction = form.querySelector('[data-secret-delete-final-action]');
    if (finalAction instanceof HTMLButtonElement) {
      finalAction.disabled = true;
      finalAction.setAttribute('aria-disabled', 'true');
      finalAction.setAttribute(
        'title',
        'Validate deletion after the latest target or confirmation change',
      );
    }
    const label = form.querySelector('[data-secret-delete-validation-label]');
    if (label) label.textContent = 'Validate Deletion';
  };

  const handleMutation = (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const form = target.closest(formSelector);
    if (!(form instanceof HTMLFormElement)) return;
    if (target.matches('[name="operation"]')) return;
    invalidateDeleteValidation(form);
  };

  document.addEventListener('input', handleMutation);
  document.addEventListener('change', handleMutation);
})();
