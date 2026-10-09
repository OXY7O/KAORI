"""One-time credential presentation must never weaken the secret boundary."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_generated_token_and_kubeconfig_use_existing_shared_ui_ownership() -> None:
    template = read('app/templates/kubernetes/tenant/credential_material.html')
    for token in (
        'components/one_time_secret.html',
        'components/operational_callout.html',
        'components/operational_section_card.html',
        'data-kaori-credential-material-result',
        '{% block dashboard_content %}',
        'Access Material',
        'id="credential-material-heading"',
        'One-time result',
        'One-time view — copy before leaving',
        'aria-label="Generated secret material"',
        "aria_label='Credential delivery instructions'",
        'md:grid-cols-3',
        'material_expires_at|user_datetime',
        'material_credential_valid_until|user_datetime',
    ):
        assert token in template, token

    assert '{% block tenant_content %}' not in template
    assert 'page_hero' not in template
    assert 'xl:grid-cols-[minmax(0,3fr)_minmax(17rem,2fr)]' not in template
    assert template.count('<h1') == 1
    assert template.count('operational_section_card.render(') == 3
    assert template.index('Credential Context') < template.index('One-time view — copy before leaving')
    assert template.index('One-time view — copy before leaving') < template.index('aria-label="Generated secret material"')
    assert template.index('aria-label="Generated secret material"') < template.index("'Delivery Workflow'")
    assert template.index("'Delivery Workflow'") < template.index("'Workflow Example'")
    assert template.index("'Workflow Example'") < template.index('Entitlement until')
    assert 'components/resource_posture_grid.html' not in template
    assert 'resource_posture_grid.render' not in template
    assert 'data-kaori-credential-context-strip' in template
    assert 'sm:grid-cols-2 xl:grid-cols-4' in template
    assert '<dl class="grid gap-px bg-outline-subtle' in template
    assert template.count('<dt class="text-xs font-semibold leading-5 text-content-muted">') == 4
    # Only the compact page heading uses text-xl; context facts use text-sm.
    assert template.count('text-xl') == 1
    assert template.count('truncate text-sm font-semibold leading-5 text-content-primary') >= 3
    assert 'min-h-32' not in template
    assert 'material_access_package.tenant_name' in template
    assert 'material_namespace' in template
    assert 'material_access_package.cluster_name' in template
    assert 'material_access_package.environment' in template
    assert 'material_access_package.service_account_name' in template
    assert 'material_access_package.access_profile' in template
    assert '{{ requested_label }}' in template
    # Truncation is only visual: the full ServiceAccount string remains the copy source.
    assert 'data-kaori-copy-root' in template
    assert 'data-kaori-copy-source' in template
    assert 'data-kaori-copy-button' in template
    assert 'data-kaori-copy-label' in template
    assert 'title="{{ material_access_package.service_account_name }}"' in template
    assert 'Copy full ServiceAccount identifier' in template
    assert 'class="block min-w-0 flex-1 truncate text-sm' in template
    shared_clipboard = read('app/static/js/clipboard.js')
    assert "button.closest('[data-kaori-copy-root]')" in shared_clipboard
    assert "root?.querySelector('[data-kaori-copy-source]')" in shared_clipboard
    assert "src=\"{{ url_for('static', filename='js/clipboard.js') }}\"" in read('app/templates/layouts/app.html')
    assert template.count('data-kaori-sensitive-material') == 0
    assert template.count('one_time_secret.material_block(') == 3
    assert template.count('material_value,') == 2
    assert template.count('material_base64,') == 1
    assert "'Human Access Token'" in template
    assert "'Namespace-Scoped Kubeconfig'" in template
    assert "'Encoded Kubeconfig (Base64)'" in template
    assert 'JumpServer' not in template
    assert 'GitHub Actions' not in template
    assert 'Helm' not in template
    assert 'RUNNER_TEMP' not in template
    route = read('app/kubernetes/tenant/routes_credentials.py')
    for title in (
        "material_title = 'Human Access Token'",
        "material_title = 'Deployment Kubeconfig'",
        "page_title = 'One-Time Human Access Token'",
        "page_title = 'One-Time Deployment Kubeconfig'",
    ):
        assert title in route, title
    assert "'GitHub Actions / Helm'" not in route
    assert "material.access_package.get('credential_type') == 'deployer_service_account'" in route
    assert "material_title = 'Approved Access Kubeconfig'" in route
    assert "delivery_label = 'Governed Individual Access'" in route
    assert "material_credential_valid_until=material.access_package.get('valid_until')" in route
    assert "material_credential_valid_until=material.expires_at" not in route
    # The sole page-level clipboard source is the non-secret ServiceAccount identifier.
    assert template.count('data-kaori-copy-source') == 1
    assert '<code data-kaori-copy-source' in template
    assert 'title="{{ material_access_package.service_account_name }}"' in template
    assert 'data-kaori-sensitive-material' not in template


def test_secret_delivery_guidance_preserves_manual_and_pipeline_contracts() -> None:
    template = read('app/templates/kubernetes/tenant/credential_material.html')
    for text in (
        "material_kind == 'token'",
        'material_access_package.jumpserver_reference',
        'material_access_package.service_account_name',
        "copy_label='Copy Token'",
        "copy_label='Copy Kubeconfig'",
        "copy_label='Copy Base64'",
        "download_name='kaori-' ~ material_namespace ~ '-kubeconfig.yaml'",
        'KAORI_KUBECONFIG_B64',
        'base64 -d',
        'umask 077',
        'mktemp',
        "trap 'rm -f",
        'kubectl auth can-i create deployments',
        "material_access_package.credential_type == 'deployer_service_account'",
        '{% if deployment_material %}',
        'Use approved individual access',
        'Remove temporary material',
        'delivery_steps',
        '{% for step_title, step_description in delivery_steps %}',
        '{{ material_access_package.jumpserver_reference }}',
        'Back to Credentials',
    ):
        assert text in template, text


def test_material_exposure_remains_one_time_no_store_and_non_persistent() -> None:
    route = read('app/kubernetes/tenant/routes_credentials.py')
    copy_component = read('app/templates/components/one_time_secret.html')
    js = read('app/static/js/tenant_credential_material.js')

    assert "response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'" in route
    assert "response.headers['Pragma'] = 'no-cache'" in route
    assert "response.headers['Referrer-Policy'] = 'no-referrer'" in route
    assert "response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'" in route
    assert "data-kaori-sensitive-material" in copy_component
    assert "data-kaori-copy-source" in copy_component
    assert "data-kaori-copy-button" in copy_component
    assert "data-kaori-download-button" in copy_component
    assert "window.addEventListener('pagehide'" in js
    assert "node.textContent = ''" in js
    assert "tenant_credential_material.js" in read('app/templates/kubernetes/tenant/credential_material.html')
