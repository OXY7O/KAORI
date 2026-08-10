from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    component = read('app/templates/components/form_with_context_rail.html')
    create = read('app/templates/kubernetes_operations/configmaps/create.html')
    standard = read('docs/design/components/FORM_WITH_CONTEXT_RAIL.md')
    form_standard = read('docs/design/components/FORM.md')
    right_rail = read('docs/design/components/RIGHT_CONTEXT_RAIL.md')
    design_readme = read('docs/design/README.md')
    quality_gate = read('scripts/quality_gate.sh')

    for token in (
        'macro layout_classes',
        'grid gap-6 xl:grid-cols-12 xl:items-start',
        'macro main_classes',
        'min-w-0 xl:col-span-8',
        'macro rail_classes',
        'min-w-0 space-y-4 xl:col-span-4 xl:sticky xl:top-5',
    ):
        require(token in component, f'Form + Right Context component missing canonical token: {token}', errors)

    for token in (
        'components/form_with_context_rail.html',
        'form_context.layout_classes()',
        'form_context.main_classes()',
        'form_context.rail_classes()',
        'ConfigMap Creation Flow',
        'Creation Safety Contract',
    ):
        require(token in create, f'Create ConfigMap must consume Form + Right Context ownership: {token}', errors)

    for copied in (
        'class="grid gap-6 xl:grid-cols-12 xl:items-start"',
        'space-y-4 xl:col-span-4 xl:sticky xl:top-5',
    ):
        require(copied not in create, f'Create ConfigMap must not copy shared form-context geometry: {copied}', errors)

    references = (
        'app/templates/cluster/add.html',
        'app/templates/prometheus/instance_form.html',
        'app/templates/alertmanager/instance_form.html',
    )
    for relative in references:
        source = read(relative)
        for token in (
            'xl:grid-cols-12 xl:items-start',
            'xl:col-span-8',
            'space-y-4 xl:col-span-4 xl:sticky xl:top-5',
        ):
            require(token in source, f'{relative} drifted from the Form + Right Context visual reference: {token}', errors)

    for token in (
        '# KAORI Form + Right Context Standard',
        'Add Kubernetes Connection',
        'Register Prometheus Connection',
        'Register Alertmanager Connection',
        'Create Kubernetes ConfigMap',
        'components/form_with_context_rail.html',
        'Do not duplicate',
    ):
        require(token in standard, f'Form + Right Context documentation missing: {token}', errors)

    require('Form + Right Context' in form_standard, 'FORM.md must document Form + Right Context as an approved layout choice.', errors)
    require('FORM_WITH_CONTEXT_RAIL.md' in right_rail, 'RIGHT_CONTEXT_RAIL.md must distinguish Form + Right Context geometry.', errors)
    require('components/FORM_WITH_CONTEXT_RAIL.md' in design_readme, 'Design README must index Form + Right Context.', errors)
    require(
        'python scripts/verify_form_with_context_standard.py' in quality_gate,
        'quality_gate.sh must run the Form + Right Context verifier.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Form + Right Context standard passed: shared 8/12 + 4/12 geometry, '
        'canonical side-box ownership, Integration visual references, and ConfigMap reuse are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
