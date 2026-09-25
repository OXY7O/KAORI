(() => {
    const form = document.querySelector('[data-resource-profile-form]');
    const payloadNode = document.getElementById('tenant-resource-profile-presets');
    if (!form || !payloadNode) return;

    let presets = {};
    try {
        presets = JSON.parse(payloadNode.textContent || '{}');
    } catch {
        return;
    }

    const fields = Array.from(form.querySelectorAll('[data-profile-field]'));
    const radios = Array.from(form.querySelectorAll('[data-profile-class]'));
    const reset = form.querySelector('[data-reset-profile]');
    const modeCopy = form.querySelector('[data-profile-mode-copy]');

    const selectedClass = () => radios.find((radio) => radio.checked)?.value || 'standard';

    const applyClass = (profileClass) => {
        const preset = presets[profileClass];
        const isCustom = profileClass === 'custom';

        for (const field of fields) {
            const key = field.dataset.profileField;
            field.disabled = !isCustom;
            if (isCustom) {
                field.value = '';
            } else if (preset?.values?.[key] !== undefined) {
                field.value = preset.values[key];
            }
        }

        if (modeCopy) {
            modeCopy.textContent = isCustom
                ? 'Custom values are editable and validated by KAORI before persistence.'
                : `${preset?.label || profileClass} preset values are auto-filled and locked. The backend enforces the same canonical contract.`;
        }
    };

    for (const radio of radios) {
        radio.addEventListener('change', () => applyClass(radio.value));
    }

    reset?.addEventListener('click', () => applyClass(selectedClass()));
    applyClass(selectedClass());
})();
