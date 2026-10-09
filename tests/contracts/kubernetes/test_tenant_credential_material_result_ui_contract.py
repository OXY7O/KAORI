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
        'components/resource_posture_grid.html',
        'components/section_intro.html',
        'data-kaori-credential-material-result',
        'Access Material Generated',
        'One-time view — copy before leaving',
        'aria-label="Generated secret material"',
        'aria-label="Credential delivery instructions"',
        'xl:grid-cols-[minmax(0,3fr)_minmax(17rem,2fr)]',
        'material_expires_at|user_datetime',
        'material_credential_valid_until|user_datetime',
    ):
        assert token in template, token

    assert template.count('one_time_secret.material_block(') == 3
    assert template.count('material_value,') == 2
    assert template.count('material_base64,') == 1
    assert "'JumpServer ServiceAccount Token'" in template
    assert "'Namespace-Scoped Kubeconfig'" in template
    assert "'GitHub Actions Secret (Base64)'" in template
    assert 'data-kaori-copy-source' not in template


def test_secret_delivery_guidance_retains_both_provider_contracts() -> None:
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
        'kubectl auth can-i create deployments',
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
