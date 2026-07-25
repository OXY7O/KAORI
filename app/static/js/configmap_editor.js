(() => {
  const formSelector = '[data-configmap-editor-form]';

  const updateConfigMapName = (form, namespaceValue) => {
    const field = form.querySelector('#configmap-name');
    if (!field) return;
    const enabled = Boolean(namespaceValue);
    field.disabled = !enabled;
    field.placeholder = enabled ? 'application-config' : 'Select namespace first';
    if (!enabled) field.value = '';
  };

  const resetConfigMapName = (form) => updateConfigMapName(form, '');

  document.addEventListener('change', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const form = target.closest(formSelector);
    if (!form) return;

    if (target.matches('[data-configmap-cluster]')) resetConfigMapName(form);
    if (target.matches('[data-configmap-namespace]')) updateConfigMapName(form, target.value);
  });

  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const form = target.closest(formSelector);
    if (!form) return;

    const addButton = target.closest('[data-add-entry]');
    if (addButton) {
      const list = form.querySelector('#configmap-entries');
      const template = form.querySelector('#configmap-entry-template');
      if (list && template instanceof HTMLTemplateElement) {
        list.append(template.content.cloneNode(true));
        window.renderKaoriIcons?.();
      }
      return;
    }

    const removeButton = target.closest('[data-remove-entry]');
    if (!removeButton) return;
    const list = form.querySelector('#configmap-entries');
    if (list && list.querySelectorAll('.configmap-entry').length > 1) {
      removeButton.closest('.configmap-entry')?.remove();
    }
  });
})();
