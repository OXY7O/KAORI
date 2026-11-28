# KAORI — Central Alert Intelligence provider coverage review (#5230)

**Authority:** #5228 central capability, #5230 provider qualification,
#5226 exact provider case reads, #5229 Vault lifecycle, #5252 recovery,
#5253 delivery, #5148 evaluator correction, existing canonical
AlertCase/Event/Audit and approved Intelligence UI standards.

**Scope:** local review on `kaori/review/staging-uat`. The read-only
Cross-Domain Alert Coverage table documents **implementation paths**, not
running provider availability, AlertCase counts, verified permission,
recovery, authorized notification or release readiness.

| Domain | Provider | Existing source path | Current qualification boundary |
| --- | --- | --- | --- |
| Kubernetes | Kubernetes | Recommendation | Committed evaluator findings; native provider-alert admission not registered |
| Object Storage | MinIO | Recommendation | Committed evaluator findings; native provider-alert admission not registered |
| Artifact Registry | Harbor | Recommendation | Committed evaluator findings; preserve dedicated registry scope and routing guard |
| Secrets & PKI | Vault | Provider alert | Exact-instance read adapter registered; local-only admission/workflow, positive recovery and delivery independently gated |
| Secrets & PKI | OpenBao | Not admitted | Inventory integration does not inherit Vault source, scope or recovery authority |
| Source Control | GitHub | Not admitted | No approved source/AlertCase adapter |
| Infrastructure Automation | Ansible | Not admitted | No approved source/AlertCase adapter |

## Runtime and authorization boundaries

- An implementation path is **not** evidence that a provider is connected,
  successfully scraped, has current authorized inventory, or has zero alerts.
- Recommendation-origin cases remain on canonical evaluator/worker paths;
  do not conflate a configured rule with committed evaluator evidence.
- Vault provider-origin cases require exact actor/instance grant, committed
  source generation, audited case admission and separately authorized
  operations. Source absence is never recovery.
- A registered provider-origin **read adapter** is not admission, positive
  recovery, outbound transport approval, or readiness for production.
- OpenBao requires its own bounded source contract and child issue under
  #5230 before being added as a provider-alert adapter. GitHub and Ansible
  remain not admitted until explicit implementation and UAT evidence exist.
- No new permission, endpoint, provider mutation, notification, automatic
  repeat, or source evaluator is introduced by this coverage display.

## Local review / evidence

1. Open Intelligence → Alert Intelligence → Overview for Kubernetes,
   Object Storage, Registry and a separately authorized Vault instance.
   Verify the same seven rows appear in the shared Violet table with
   responsive horizontal overflow, semantic headers and light/dark styles.
2. Verify an unauthorized Vault instance still cannot enumerate or read
   provider cases; a rejected provider source does not appear as Available.
3. Run the existing checks when consolidated Dev Container local testing
   is approved (not executed during code-first construction):

   ```bash
   ruff check app/intelligence/alert_intelligence/provider_coverage.py app/intelligence/alert_intelligence/provider_case_scope.py tests/contracts/intelligence/test_alert_provider_coverage_contract.py
   ruff format --check app/intelligence/alert_intelligence/provider_coverage.py app/intelligence/alert_intelligence/provider_case_scope.py tests/contracts/intelligence/test_alert_provider_coverage_contract.py
   python -m djlint app/templates/intelligence/partials --check
   python -m pytest -q -p no:cacheprovider tests/contracts/intelligence/test_alert_provider_coverage_contract.py
   ```

Record the tested commit SHA and browser/role evidence. The actual Vault
exporter, independent signed resolution/destination authority, disposable
notification channel, PostgreSQL concurrency UAT and human acceptance
are still pending under #5252/#5253. This display is not a workaround.


## Operator workflow

Keep one central workspace. Select an authorized scope, review its committed
summary, triage Active Alerts, and use Resolved for positive recovery,
independent verification and closure. The implementation matrix is visible
even without an authorized instance but never exposes cases from another
scope. Provider templates, provider-native silences and automatic routing
remain Reserved Plan unless separately qualified. Local Vault delivery
uses an exact scoped routing candidate and independent signed approval;
generic replay does not mutate or resend its manual-only delivery journal.

Review-only code is not production availability. The external recovery
producer, independent destination authority, actual provider test and
PostgreSQL concurrency UAT remain prerequisites.
