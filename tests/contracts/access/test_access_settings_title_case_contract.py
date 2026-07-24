from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[3] / 'app' / 'templates'

FORBIDDEN_PRESENTATION_COPY = {
    'settings/permissions/index.html': (
        'Read-only, code-owned',
        'Permission registry',
        'All modules',
        'No matching permissions',
        'How RBAC is applied',
        'Role coverage',
        'Adding a permission',
    ),
    'settings/reports/partials/_placeholder.html': (
        'Planned configuration surface',
        'Report settings are being defined',
    ),
    'settings/roles/index.html': (
        'Default baseline, custom extension',
        'Role registry',
        'All types',
        'Default roles',
        'Custom roles',
        'All statuses',
        'Effective permissions',
        'No matching roles',
        'Default baselines',
        'All role types',
    ),
    'settings/roles/form.html': (
        'Protected default role',
        'Review the role configuration',
        'Role configuration',
        'Role identity',
        'Operational purpose',
        'Permission matrix',
        'Role summary',
        'Access guardrails',
    ),
    'settings/secret_reveal/index.html': ('Global reveal remains disabled',),
    'settings/data_lifecycle/partials/_domain_workspace.html': (
        'Default operation',
        'Archive then cleanup',
        'Archive only',
    ),
    'users/providers/form.html': ('Provider identity and state',),
    'users/providers/index.html': (
        'No external provider configured',
        'How each provider is used',
    ),
    'users/reset_password.html': (
        'Validation error',
        'Administrative credential recovery',
        'Reset impact',
    ),
}


def test_access_and_settings_presentation_titles_use_title_case() -> None:
    failures: list[str] = []
    for relative_path, forbidden_values in FORBIDDEN_PRESENTATION_COPY.items():
        content = (TEMPLATES / relative_path).read_text(encoding='utf-8')
        for value in forbidden_values:
            if value in content:
                failures.append(f'{relative_path}: {value!r}')

    assert not failures, 'Sentence-case presentation copy remains:\n' + '\n'.join(failures)
