from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_native_namespace_can_attach_to_existing_tenant_without_duplicate_tenant_creation():
    preflight = read('app/kubernetes/tenant/discovery_service.py')
    adoption = read('app/kubernetes/tenant/discovery_adoption.py')
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    routes = read('app/kubernetes/tenant/routes.py')

    assert "row = {" in preflight
    assert "'tenant_adoption_existing_environments': existing_tenant_environments" in preflight
    assert "Tenant.provider_key == 'native_kubernetes'" in preflight
    assert "Tenant.lifecycle_status == 'ready'" in preflight

    assert 'name="attach_environment_id"' in ui
    assert 'name="provider_uid"' in ui
    assert 'name="provider_resource_version"' in ui
    assert 'Attach to {{ option.tenant_name }}' in ui
    assert 'not expanded automatically' in ui

    assert 'def attach_discovered_native_namespace_committed(' in adoption
    assert "provider_key') or '') != 'native_kubernetes'" in adoption
    assert 'validate_namespace_attachment_uid(' in adoption
    assert 'validate_adoption_provider_identity(' in adoption
    assert "expected_resource_version=str(source.get('provider_resource_version')" in adoption
    assert '_native_management(' in adoption
    assert '_managed_namespace_map([cluster_id])' in adoption
    assert '_native_namespace_record(context, environment' in adoption
    assert '_take_over_native_allocation(context, record)' in adoption
    assert 'tenant.provider_evidence_json = existing_evidence' in adoption
    assert "'grants_expanded_automatically': False" in adoption
    assert 'reconcile_access_grants_for_namespace_committed(' not in adoption

    assert 'attach_discovered_native_namespace_committed(request.form)' in routes
    assert 'adopt_discovered_tenant_committed(request.form)' in routes
    assert "'Native Namespace Attached · Managed Allocation'" in routes
    assert "(namespace.provisioning_evidence_json or {}).get('provider_mutation_performed')" in routes
    assert "'operation': 'attach_existing_tenant_namespace' if attach_existing" in routes
    assert "'provider_mutation_may_have_started': not (" in routes
    assert 'KAORI database rollback' in routes
    assert 'provider_attempt_started = False' in routes
    assert "'provider_mutation_may_have_started': provider_attempt_started and not (" in routes
    assert "'submitted_preflight_provider_uid': request.form.get('provider_uid')" in routes
    assert "'submitted_preflight_resource_version': request.form.get('provider_resource_version')" in routes
    assert "'attach_existing_tenant_namespace'" in routes


def test_native_adoption_checks_capsule_owner_references_at_submit():
    adoption = read('app/kubernetes/tenant/discovery_adoption.py')
    discovery = read('app/kubernetes/tenant/discovery_service.py')
    mutator = read('app/kubernetes/tenant/allocation_cutover.py')

    assert adoption.count("owner_references=getattr(metadata, 'owner_references', None)") == 2
    assert discovery.count("owner_references=getattr(metadata, 'owner_references', None)") == 2
    assert 'capsule_namespace_authority_present(' in mutator


def test_native_adoption_destination_is_mutually_exclusive_for_create_and_attach():
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    js = read('app/static/js/tenant_adoption_modal.js')

    assert 'data-tenant-adoption-destination' in ui
    assert 'data-tenant-adoption-create-fields' in ui
    assert 'data-tenant-adoption-attach-fields' in ui
    assert 'name="tenant_name"' in ui
    assert 'name="environment"' in ui
    assert 'name="attach_environment_id"' in ui
    assert 'data-tenant-name="{{ option.tenant_name }}"' in ui
    assert 'data-environment-name="{{ option.environment|title }}"' in ui
    assert 'data-tenant-adoption-target-tenant' in ui
    assert 'data-tenant-adoption-target-environment' in ui
    assert 'Attach Namespace to Existing Tenant' in ui
    assert 'no Tenant is created' in ui
    assert 'Tenant identity and destination Environment are taken from the selection above' in ui

    assert 'const syncAdoptionDestination = (modal) =>' in js
    assert 'Boolean(destination.value.trim())' in js
    assert "createFields.classList.toggle('hidden', isAttachment)" in js
    assert "createFields.classList.toggle('grid', !isAttachment)" in js
    assert "attachFields.classList.toggle('hidden', !isAttachment)" in js
    assert 'field.disabled = isAttachment' in js
    assert 'field.required = !isAttachment' in js
    assert "createFields.querySelectorAll('[name=\"tenant_name\"], [name=\"environment\"]')" in js
    assert 'selected?.dataset.tenantName' in js
    assert 'selected?.dataset.environmentName' in js
    assert 'tenant.textContent' in js
    assert 'environment.textContent' in js
    assert "syncAdoptionDestination(modal)" in js
    assert "document.addEventListener('change'," in js


def test_adoption_confirmation_result_and_submit_action_follow_selected_mode():
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')

    assert ui.count('data-tenant-adoption-create-copy') >= 6
    assert ui.count('data-tenant-adoption-attach-copy') >= 6
    assert 'data-tenant-adoption-attach-copy class="hidden"' in ui
    assert 'Adopt & Manage' in ui
    assert 'Attach Namespace</span>' in ui
    assert 'Namespace Attached · Managed Allocation' in ui
    assert 'Existing Tenant identity retained; Namespace allocation is managed' in ui
    assert 'Existing Access Grants are not expanded automatically' in ui
    assert 'This is not an observation-only action.' in ui
    # The original Capsule-only pathway remains explicit and untouched.
    assert '{% if tenant_adoption_attachment_only %}' in ui
    assert 'Attach Capsule Namespace' in ui
    assert 'Adopted / Provider Mirrored' in ui


def test_review_adoption_preflight_modal_survives_htmx_swap_target_variants():
    discovery = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')
    preflight = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    unavailable = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight_error.html')
    js = read('app/static/js/tenant_adoption_modal.js')
    page = read('app/templates/kubernetes/tenant/tenants.html')

    assert 'data-tenant-adoption-load' in discovery
    assert 'hx-target="#tenant-adoption-preflight-slot"' in discovery
    assert 'id="tenant-adoption-preflight-slot"' in discovery
    assert 'data-tenant-adoption-modal' in preflight
    assert 'data-tenant-adoption-modal' in unavailable
    assert "js/tenant_adoption_modal.js" in page

    # The HTMX target may be exposed through detail.target rather than event.target.
    assert "event.detail?.target || event.target" in js
    assert "target.id === 'tenant-adoption-preflight-slot'" in js
    assert "document.addEventListener('htmx:beforeRequest'" in js
    assert "opener = requestElement" in js
    assert "preflightPending = true" in js
    assert "document.addEventListener('htmx:afterSwap'" in js
    assert "document.addEventListener('htmx:afterSettle'" in js
    assert "document.addEventListener('htmx:afterRequest'" in js
    # The HTML response must be visible without waiting for any HTMX callback.
    for fragment in (preflight, unavailable):
        assert 'data-tenant-adoption-modal' in fragment
        assert 'class="fixed inset-0 z-[90] flex items-center justify-center' in fragment
        assert 'aria-hidden="false"' in fragment
        assert 'class="fixed inset-0 z-[90] hidden items-center' not in fragment

    assert "modal.dataset.tenantAdoptionActivated !== 'true'" in js
    assert "modal.dataset.tenantAdoptionActivated = 'true'" in js
    assert "delete modal.dataset.tenantAdoptionActivated" in js
    # Form-specific sync cannot prevent the modal itself becoming visible.
    open_modal = js.split('const openModal = (modal, button = opener) => {', 1)[1]
    open_modal = open_modal.split('const closeModal = (modal) => {', 1)[0]
    assert open_modal.index("modal.classList.remove('hidden')") < open_modal.index(
        'syncAdoptionDestination(modal)'
    )

    assert "if (load) reportPreflightFailure(event)" in js
    assert "A successful afterRequest may precede the HTML swap" in js
    assert "if (!revealPreflight(event)) reportPreflightFailure()" not in js
    assert "event.detail?.successful === false" in js
    assert "message.setAttribute('role', 'alert')" in js
    assert "message.setAttribute('data-tenant-adoption-request-error', '')" in js
    assert "Adoption preflight request failed (HTTP" in js
    assert "event.detail?.xhr?.status" in js
    assert "message.append(title, guidance)" in js
    assert "guidance.textContent" in js
    assert "event.detail?.xhr?.responseText" not in js
    assert "status >= 500" in js
    assert "kind === 'target'" in js
    assert "document.addEventListener('htmx:responseError'" in js
    assert "'targetError', 'swapError'" in js

    # HTMX replacement must not require per-page script initialization.
    assert "document.addEventListener('click'" in js
    assert "document.addEventListener('change'" in js
    assert "syncAdoptionDestination(modal)" in js


def test_adoption_preflight_templates_parse_as_valid_jinja() -> None:
    # Parse with Jinja itself, not only delimiter counts. This catches
    # malformed tags such as '{% endif %>' before the preflight GET reaches UAT.
    environment = Environment(autoescape=True)
    for template in (
        'app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html',
        'app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight_error.html',
    ):
        source = read(template)
        assert '%>' not in source
        environment.parse(source)
