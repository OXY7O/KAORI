# KAORI — Integration Provider Selection UAT

## Authority and standard

Issue #3106 establishes the approved provider-first registration workflow for
the six Integration domains: Orchestration, Observability, Storage, Registry,
Secrets Management, and Source Control.

**Domain → Integration Type → Choose Provider → Provider-Owned Register Connection.**

The Integration Provider Matrix remains authoritative for available versus
unavailable providers. Existing provider routes and Flask-WTF forms retain
credential, compatibility, CSRF, permission, and validation authority. The
canonical Metrics Source selector is preserved, including Prometheus and
Thanos Query. No invented registrations for matrix entries that are not
available.

## Registration entrypoints

| Integration type | Available provider | Provider-owned registration endpoint |
| --- | --- | --- |
| Container Orchestrator | Kubernetes | `cluster.add_cluster` |
| Metrics Source | Prometheus / Thanos Query | Existing `integrations.select_metrics_source_provider` → `integrations.register_metrics_source` |
| Alert Source | Alertmanager | `alertmanager.new_instance` |
| Object Storage | MinIO | `minio.new_instance` |
| Registry | Harbor | `harbor.new_instance` |
| Secrets & PKI | HashiCorp Vault | `vault.new_instance` |
| Source Control | GitHub | `github_source.new_connection` |

File/Block Storage and other matrix entries remain visible as unavailable,
without actionable registration. Notification Channels retain the established
channel-type chooser and channel-specific form workflow rather than being
incorrectly modeled as infrastructure-provider matrix entries.

The domain CTA uses the reusable provider selector
`integrations.choose_integration_provider`. Registration actions in the
provider frontpages likewise go to the selector, not straight to credential
forms. Provider overview/registry, saved connections, bindings, and all
operational routes remain independent and unchanged.

## Metrics Source provider chooser visual refinement (#3112)

The existing `/integrations/observability/metrics-sources/new` selector
retains Prometheus and Thanos Query provider-defined registration URLs.
Its Hero context helper is now **"Adapters own validation and runtime."**
to fit a single line on the reviewed desktop reference without forced
nowrap or truncation at mobile breakpoints.

Provider cards use the same Violet border/hover treatment as the shared
cross-domain selector. **Adapter**, **Query Language**, and the main
**Guide** use the current anchored KAORI `info_tip.render` macro for
pointer, keyboard and touch. The longer explanation is in the popovers
rather than crowding the visible hero. Shared responsive columns and
the existing primary registration button are preserved.

**Human visual UAT / executable QA pending:** review at 1440×900 and
a narrow viewport in light/dark mode. Check the context helper is one
line on desktop, hover or focus reveals correct guidance, card focus
and registration actions work, and both existing Prometheus / Thanos
provider forms open without altering credentials.

```bash
python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_metrics_source_routing_audit_20260817_contract.py
djlint --check \
  app/templates/integrations/observability/metrics_source/provider_selector.html
```

## Functional Dev Container UAT

1. For each of the six Integration domain pages, use its **Open** action.
   Verify the selector lists matrix providers, makes only available choices
   actionable, and does not send users directly to a registration form.
2. For Observability check both Metrics Source (Prometheus, Thanos Query)
   and Alert Source (Alertmanager). Choose each available provider and
   confirm its **existing** registration page opens.
3. For Storage choose MinIO; for Registry choose Harbor; for Orchestration
   choose Kubernetes; for Secrets Management choose Vault; for Source Control
   choose GitHub. Verify **Back to Integrations** and the provider selection
   state, including narrow/mobile viewport and light/dark.
4. Confirm provider frontpage **Register Connection** actions enter the
   same selector before opening provider-specific configuration.
5. Check hover/click/focus on standard KAORI guide/info tips, the Hero
   single-line helper on desktop, button and card focus styling, and correct
   non-actionable unavailable cards.
6. Do not provide secrets during initial navigation UAT. Run connection
   registration, Test Connection, Full Validation, and committed evidence
   checks under each provider's existing functional runbook.

## Checks

```bash
python -m ruff check app/integrations/routes.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py

python -m ruff format --check app/integrations/routes.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py

python -m pytest -q -p no:cacheprovider \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py \
  tests/contracts/integrations/test_integration_domain_navigation_contract.py \
  tests/unit/test_source_control_github_kernel_contract.py \
  tests/ui/test_source_control_github_app_onboarding_contract.py \
  tests/ui/test_source_control_sidebar_navigation_contract.py

djlint --check \
  app/templates/integrations/provider_selector.html \
  app/templates/integrations/partials/_domain_workspace.html
```

**Evidence state:** implementation/source review only; executable Dev
Container results and browser Human Acceptance are **pending**. No official
CI/CD/Developer Check/Full Admission, promotion to `kaori/staging` or main,
deployment, tag, or release until explicitly authorized.
