# Vault Metrics Source binding — HV-06 (#2590)

## Authority and registered source

Vault is authoritative for Secret/PKI/lifecycle facts; Vault telemetry is
scraped by Prometheus (optionally queried through Thanos for long retention).
KAORI does **not** implement a Vault-specific TSDB or copy metrics into KV v2
inventory. Its Metrics Source registry remains responsible for connection
validation, selector binding, query.instant/query.range and source routing.
The source is configured in `Integrations → Observability → Metrics Source`,
not on an embedded Vault telemetry dashboard.

## Vault scrape prerequisites

For supported Vault installations, configure Prometheus with:
- HTTPS target and approved CA/trust; `metrics_path: /v1/sys/metrics`.
- Appropriate read-only token custody in the Prometheus scrape configuration,
  not inside KAORI ordinary evidence or Git.
- Prometheus relabel/static target label `vault_instance: "<KAORI IntegrationInstance.id>"`
  where the value is the numeric KAORI canonical Vault provider identity.
- A qualified `vault_core_active` gauge that is query-visible at the selected
  Prometheus/Thanos source and has a bounded sample age.

HashiCorp `/sys/metrics` requires the **root namespace**. Active/standby
and CE/Enterprise behavior differ; a working Vault health API does not imply
scrape permissions or metrics on every node. Verify the scrape is actually
exposed and matches the supported metric naming profile.

Official source references:
- https://developer.hashicorp.com/vault/api-docs/system/metrics
- https://developer.hashicorp.com/vault/docs/configuration/telemetry
- https://developer.hashicorp.com/vault/docs/internals/telemetry/metrics/core-system

## First admitted review contract

The existing Metrics Source Managed Asset type `vault_instance` is bound to
one canonical IntegrationInstance ID. The `prometheus_http` adapter now
registers `vault-telemetry-v1` with the ordinary `binding.validate` path.

The current one-matcher form requires exactly:
`vault_instance=<numeric IntegrationInstance.id>` with `=` operator.
The validator issues only a bound, read-only
`vault_core_active{vault_instance="<id>"}` query and qualifies exactly one
0/1 signal whose sample is no older than five minutes. Zero series are
**degraded**, multiple series with the same Vault instance identity are
**blocked as ambiguous**, and target-name/regex matching is not accepted as
equivalent to canonical provider identity.

This strict profile does not claim complete HA cluster coverage. Multi-target
HA profiles must use additional independently qualified node/cluster
selectors, explicit freshness and retention and their own accepted binding
validation. A single matching standby gauge is an identity signal, not
proof of Vault availability or active leadership.

**Not yet delivered:** qualified multi-day/long-term retention,
source-owned metrics history/materialization, Vault-specific Analytics queries,
HA/federation profiles, AlertCase enrichment/routing and real Prometheus/Thanos
UAT. The independently validated recent-hour source probe described below
must not be mistaken for a materialized historical dataset. None of these
optional telemetry gaps can downgrade core Vault API readiness. The Vault operational Overview continues to show
missing metrics as **not bound/not materialized** until approved read models
exist.

Focused tests authored:
`tests/integrations/test_vault_metrics_binding.py`.

Use existing KAORI validation and security gates, including Prometheus/Thanos
negative tests, per-source label/scope checks, Developer Check and real
DevContainer UAT. No readiness PASS has yet been observed.


## Vault Alert Source / Alertmanager consumer (HV-06 follow-up)

The existing Alertmanager provider owns API v2 alert retrieval, silences,
routing, grouping and source readiness. The canonical `IntegrationBinding`
for `vault_instance` uses the `vault-alerts-v1` profile. In the
Alertmanager Bindings & Consumers workspace, select the canonical Vault
instance and configure the exact equality matcher:

```text
vault_instance="<KAORI IntegrationInstance.id>"
```

Use the **same** `vault_instance` value on the Prometheus/Alertmanager rule
labels for that Vault deployment. It is not supplied by Vault automatically.
A healthy Alertmanager API with zero active matching alerts is not evidence
that Vault has no failures: `identity_observed=false` remains explicit.
Other Vault instances and global unmatched alerts must not be attributed
to the selected asset.

The source binding is validated on creation/update and again at runtime.
Unknown or retired Vault instances, regex/broad/noncanonical selectors
and foreign alert labels are blocked. The Vault binding stores counts and
capability flags but suppresses sample alert names, which may themselves
contain sensitive Secret paths. Provider failure messages are sanitized.

Alertmanager source eligibility is **independent** of the Vault API,
KV v2 collection state, and Prometheus historical coverage. Binding alone
does not create new Prometheus alerting rules, AlertCases, enrichment,
receiver routing, webhook paths or an alert notification engine. Those
are covered by the existing Central Alert Intelligence and #2596.

Required UAT: register approved Alertmanager source, bind and validate an
approved Vault instance with no alerts and a representative matching
alert, reject mismatched identities, confirm per-role direct access
and ensure provider outage does not mutate Vault readiness. Do not
declare binding acceptance without those checks.

Focused tests:
`tests/integrations/test_vault_alert_source_binding.py`.

Provider API source: https://github.com/prometheus/alertmanager/blob/main/api/v2/openapi.yaml


## Bounded historical query-range qualification — HV-06 #2697

An explicit Vault Metrics Source **Validate Binding** now first qualifies the
existing exact single-node instant `vault_core_active` identity. If that succeeds,
the same registered Prometheus-compatible client requests **one** bounded
`query_range` over the most recent 60 minutes at a 300-second step.

The validator checks exact `vault_instance` identity, one matrix series,
finite/monotonic timestamp and 0/1 values, endpoint coverage and no gap
exceeding ten minutes. It retains only sanitized evidence status/count/step:
`recent_hour_qualified`, `incomplete`, `ambiguous`, `unavailable`, or
`not_validated`. A qualified recent hour stores
`retention_coverage=one_hour_observed_only` and **does not establish**
historical retention beyond that hour, HA topology, continuous workload
health, Vault API availability, service impact or time-series materialization.

Range unavailable/denied/malformed/missing never upgrades retention, but
also **does not downgrade** already-qualified instantaneous identity nor core
Vault provider readiness. No provider tokens, host/metric label values,
timeseries points or raw response/errors are committed. Prometheus/Thanos
remains authoritative; no new TSDB/worker/query endpoint is introduced.
Existing binding validation evidence ownership remains unchanged.

The real Prometheus/Thanos range API, worker/network performance, HA and
long-term retention require DevContainer/staging UAT. Test source:
`tests/integrations/test_vault_metrics_binding.py`.

## Committed binding-coverage projection (HV-06 #2767)

The Secrets & PKI **Operational Overview** no longer unconditionally labels
Vault Metrics and Alert sources as `Not Bound`. The bounded read-only
`build_vault_binding_coverage` reads canonical `IntegrationInstance` and
`IntegrationBinding` records, never calls Prometheus/Thanos or Alertmanager
during HTTP rendering, and emits only source-neutral summary labels/counts.

For active approved Vault instances (max 25, binding rows max 100), it
qualifies **one** source binding per instance only when:
- `asset_type=vault_instance` and `asset_key` exactly equals the canonical
  `IntegrationInstance.id` decimal string;
- the source IntegrationInstance is active, enabled and in its own
  `metrics_source` / `alert_source` integration family;
- validation profile is `vault-telemetry-v1` / `vault-alerts-v1`;
- validation status is `ready`, timestamp is not in the future and no older
  than 24 hours; multiple independently ready bindings are not counted as
  single-source qualification.

Stale/disabled/incomplete/unbound/error states are **not qualified**.
Qualification here means **committed identity binding validation**, NOT
live health, complete HA/federation coverage, historical Metrics Source
retention, observed alert absence, AlertCases, routing or delivery success.
Source IDs, selectors, raw alerts, Secret names, paths, Vault credentials
and provider response payloads never enter this fleet-level view.
Source-specific drilldown continues to require each Integration capability's
existing authorization. Exact-SHA DevContainer tests/UAT remain required.

## HV-12 bounded Vault source alert evidence (#2786)

During the existing **explicit Alert Source Validate Binding**, the canonical
Alertmanager provider now evaluates up to 100 returned Vault alert rows. Each
must carry the exact approved `vault_instance` identity. The only committed
additional metadata is a safe, allowlisted `vault_alert_sample` evidence
record: sample state and counts grouped by Alertmanager active/suppressed/
unprocessed status and critical/warning/info severity.

An empty response is `unobserved`, with unknown counts; an invalid source
identity, unexpected response shape or over-budget row population is `blocked`.
Missing/unrecognized lifecycle or severity evidence is `incomplete` and
downgrades only consumer binding validation. Partial counts are discarded.
Sensitive alert names, paths, labels, annotations, fingerprints, URLs,
credentials and source responses are never committed by this new summary.
Previous evidence is cleared on blocked validation.

This is a **point-in-time binding-validation sample**, never a live AlertCase,
current firing/silence count, confirmed health, root cause, service impact,
recovery, escalation or successful notification. There is no polling, new
runtime read path, AlertCase promotion, alert routing, provider mutation or
implicit cross-tenant authorization. Later HV-12 work requires separate
governed committed source snapshots, case ownership and access controls.
Focused tests: `tests/integrations/test_vault_alert_source_qualification.py`.
Exact-SHA local and provider DevContainer UAT remain required.

## HV-12 committed validation sample summary (#2791)

The provider-neutral Secrets & PKI Operational Dashboard > Signals & Actions
projects last validated, committed **Vault Alert Source** sample totals.
Both `secrets_pki.view` (route authority) and `intelligence.view` are
required to read/display those totals; without the latter, the read model is
not called. No path/name/serial, raw alert or source identity is rendered.

The projection is bounded to 25 active Vault identities and 100 enabled
Alert Source bindings, requires one and only one binding per Vault,
exact canonical `vault_instance` selector, active Alertmanager integration,
`vault-alerts-v1` profile and a ready validation no older than 24 hours.
The validation snapshot must be `qualified` with internally consistent,
nonnegative totals, at most 100 observed rows per source. Only the **fully
qualified population** produces counts, never a partial or stale subset.
An empty accepted source sample is `unobserved`, not zero. Duplicate,
foreign, incorrect-profile, stale or malformed source evidence produces
blocked/partial/needs-validation/unavailable as appropriate with unknown counts.

The displayed validation time is the **earliest** validated timestamp across
the fully qualified population. This is neither live Alertmanager status
nor current firing, a canonical AlertCase, source recovery, Vault API health
or delivery/notification success. Normal operational GET does not contact
Vault/Alertmanager. Tests:
`tests/integrations/test_vault_alert_source_sample_summary.py`.
Exact-SHA DevContainer and human UAT remain pending.

## HV-12 per-alert committed correlation seam (#2798)

The existing `AlertSignalSnapshot` model now supports an internal-only,
source-qualified `secrets_pki.vault_alertmanager_observations` signal.
`commit_vault_alert_observations` accepts one **trusted worker-provided**
Alertmanager payload (it does not query the provider or create a job).
A real worker/JobExecution invocation is **not wired by this child**:
no data is collected automatically and no operational UI reads these
per-alert observations.

Admission requires an active canonical Vault instance, exactly one active
Alertmanager binding, exact `vault_instance` equality selector, the
`vault-alerts-v1` ready validation profile and validation no older
than 24 hours. Maximum 100 alert rows. Every row requires an exact Vault
identity, allowlisted Alertmanager state/severity, native 16-character
hex fingerprint, and timezone-qualified startsAt. Missing, foreign,
duplicate, malformed or over-budget source responses fail closed.

The caller supplies a **dedicated stable secret key >=32 bytes**, retained
only in process memory. Use an approved secret manager for this key when
the worker is wired; NEVER use a hardcoded/demo secret or pass key material
through HTTP, job metadata, logs or committed evidence. KAORI uses Python
stdlib `hmac` with SHA-256 and source/Vault/occurrence domain separation
to commit **opaque correlation handles**, not native fingerprints, alert
names, path/namespace/role labels, annotations, URLs or tokens. Source
identity and occurrence startsAt are also required: matching hostnames,
alert names, timestamps or paths are never used as join evidence.
Key rotation invalidates handle continuity unless an explicitly reviewed
key-version migration/correlation strategy is provided.

A successful observation has five-minute TTL and records only
allowlisted handle/state/severity/starts_at plus internal source binding
provenance. A failed trusted observation invalidates prior ready payload
with a generic error. Replayed observations cannot overwrite a newer
generation. An empty result is `unobserved`, not zero healthy alerts;
expired/failed/unauthorized/unobserved evidence **never** establishes
resolution. `read_vault_alert_observations` is internal-only. Calling
code must enforce the approved #724 resource-scope authorization before
any user-facing view; no HTTP route or AlertCase promotion is provided.

Before UAT acceptance: register the approved provider-owning worker
JobExecution and stable correlation secret, verify the actual Alertmanager
query/source/binding identity, replay and failure paths, scoped RBAC,
retention and lifecycle against the exact source SHA. Do not claim live
AlertCase firing, resolution, notification or recovery.
Focused tests: `tests/intelligence/test_vault_alert_observation_snapshot.py`.

## HV-12 manually registered JobExecution source producer (#2802)

Jobs & Executions now registers `secrets_pki.vault_alerts.observe` as a
**manual-only** definition. The database policy defaults disabled and
`schedule_supported=false`; no Celery Beat or automatic polling is added.
Only an actor with `jobs.execute` and `secrets_pki.sync` can trigger
`Run Now`; existing `jobs.view` governs Job Configuration access.

The job dispatcher selects at most 25 active canonical Vault identities and
only their **single currently qualified Alertmanager source binding**.
It enqueues numeric binding IDs and sanitized source-count metadata through
`enqueue_canonical_job` on `inventory`. A registered-worker preflight
prevents dispatch to workers missing the new task. The worker verifies its
canonical JobExecution ID, task ID and active status, and rechecks the exact
Vault instance/source binding at execution. It uses existing Alertmanager
API v2 client credentials and requests `GET /api/v2/alerts` with the
equality filter `vault_instance="<canonical ID>"`. A missing, disabled,
invalid, expired or ambiguous binding is rejected without a fallback query.
There is no request-time polling from Secrets & PKI operational dashboards.

**Worker-only secret:** before DevContainer UAT, provision a stable,
random, independent HMAC key as a hex-encoded environment secret named
`KAORI_VAULT_ALERT_CORRELATION_HMAC_KEY_HEX` (32-64 bytes, 64-128 hex chars)
**only to the trusted worker runtime** using approved secret custody.
There is no default/demo key or fallback to integration credentials.
Never place the value in Git, `.env.example`, JobPolicy, JobExecution,
Celery args/results, logs, tickets, screenshots or user-visible errors.
The worker fails closed if the key is not configured or malformed.
Rotating that key requires a separately reviewed correlation migration;
blind rotation breaks handle continuity.

The existing Environment Contract gate verifies that only
`app/intelligence/alert_signals/vault_jobs.py` reads this worker-only key.
Its name must remain absent from shared development, production and standalone
RC environment templates. Inject it through approved **worker-scoped** secret
custody, never through a shared Flask/web/Beat environment file.

The bounded provider result is passed only in worker memory to the existing
source-qualified snapshot writer: max 100 alerts, strict identity and
occurrence validation, opaque HMAC handles, five-minute TTL. Error paths
retain generic JobExecution/AlertSignalSnapshot failure state without provider
response text. A valid empty sample is **unobserved**, not all-clear.
Missing or stale samples cannot resolve AlertCases. No alerts are created,
promoted, routed, sent or resolved by this job; no privileged Vault operation
exists. Source provider readiness remains independently authoritative.

Tests authored: `tests/intelligence/test_vault_alert_job_producer.py`.
At UAT, verify selected Alertmanager API source, worker task registration,
queue routing, denied actor, real filtered response, malformed/foreign
response, provider outage, last-known snapshot invalidation, HMAC key custody
and no AlertCase/routing side effects. Real DevContainer tests, PostgreSQL
integration and human acceptance remain **Not Tested**.

## HV-12 internal provider AlertCase correlation plan (#2807)

The Central Alert Intelligence layer now has
`build_vault_provider_case_plan(binding_id=...)`, an **internal, read-only**
correlation planner. It consumes only the qualified, five-minute
`AlertSignalSnapshot` from the canonical Vault Alertmanager binding.
No web endpoint or JobExecution producer calls it yet. It never writes
`AlertCase`, `AlertCaseEvent`, routing policy, notifications or audit.
The provider remains authoritative.

The prospective identity is `vault-alert:<opaque HMAC handle>` and is exact
across Vault/Alert Source/occurrence. Matching is limited to provider-origin
cases under canonical `secrets_pki` / `vault_instance` scope with exact
source binding and source integration provenance. It rejects duplicate
case keys, historical replay ambiguity, foreign/cross-scope case-key
collisions, unrecognized prior provenance, enabled routing, and >100 scoped
case records. There are no path/name/hostname/time-only joins.

Only fresh committed `firing` observations qualify as create candidates.
Existing exact firing cases can qualify as refresh candidates.
Suppressed/unprocessed observations and previous cases missing from the
latest snapshot are `retain_unverified` / `review_source` only, never
resolved. Closed historical cases are held for explicit review, not reopened.
Unobserved, failed, expired or disabled source observations result in no
per-case plan and no inference that Vault, consumers or alerts recovered.
Plan rows propose `routing_state=suppressed` for a future separately
approved write path. All correlation handles and case IDs are internal
security-sensitive metadata and are not exposed through a route/UI/API.

**Not implemented:** actual provider-origin case admission, case writes,
audited lifecycle transitions, scoped case UI, routing/notification policies,
confirmed source-resolved semantics or automatic source polling. These must
be a separately owned child issue after #724 authorization and real
Alertmanager/DevContainer UAT.
Focused tests: `tests/intelligence/test_vault_provider_case_plan.py`.

## HV-12 default-disabled provider AlertCase admission (#2813)

Central Alert Intelligence includes an internal `admit_vault_provider_cases`
command which **has no route, no scheduled job, and no producer invocation**.
It is disabled unless trusted runtime configuration explicitly sets
`KAORI_VAULT_PROVIDER_CASE_ADMISSION_ENABLED=true`. Never enable this
in production before approved #724 scope controls, provider UAT and
human acceptance. Changing this env var alone does not schedule a job.

The command requires an active persistent actor granted
`intelligence.decisions.create`, `intelligence.view`,
`secrets_pki.sync`, and `secrets_pki.view` simultaneously. Admission
takes an exclusive PostgreSQL row lock on the exact source binding and
committed signal generation and recomputes the HV-12 candidate plan under
that transaction. At most ten new cases can be admitted per command, or
the entire operation is blocked without a partial insert.

Only `create_candidate` and `refresh_candidate` permit writes; case
identities are HMAC-scoped. All provider-origin cases remain
`routing_state=suppressed`, `routing_override_reason=policy_ineligible`,
and never deliver notifications. Evidence contains only the canonical
binding/source IDs and the fixed correlation profile; no raw fingerprint,
alert labels/annotations, path, summary, URL or secrets are persisted.
Audit and case timeline events contain only allowlisted generic metadata.
Repeated reads of one source generation are idempotent. Missing, stale,
unobserved, suppressed, unknown, closed and absent source occurrences
**never** trigger case resolution, reopening or closure.

No change to the existing recommendation-scoped Alert Intelligence workspace
is included; operator access to provider-origin cases remains **unapproved**
pending separate source-scoped RBAC/route/HTML workstream. This command is
for contract testing and controlled review only, not production activation.
Tests: `tests/intelligence/test_vault_provider_case_admission.py`.


## HV-12 #2821 scope and recovery security finding closure (source change, not UAT)

Review identified two blockers in the earlier holding implementation:
(1) provider-origin case admission checked only global role/Super Admin
permission without an approved target Vault-instance resource grant;
(2) the scoped provider-case view accepted an unsupported `resolved`
source state. The internal writer now checks an active normalized role
and the existing #724 approved exact-instance grant under the canonical
binding transaction lock, with no mount inheritance or global Super Admin
shortcut. The workspace now blocks `resolved` source rows pending future
provider recovery evidence. The writer is still default-disabled and
disconnected from runtime callers; routing/notifications remain suppressed.
These source remediations **do not constitute DevContainer UAT PASS**.
See the HV-12 #2821 scenario matrix in `VAULT_INTEGRATED_UAT.md`.

## HV-12 serialized committed observation generation (#5241)

Both internal observation writers (qualified response and transport failure) acquire the existing exact source binding lock before the snapshot generation lock, matching the case admission transaction. The writer refreshes committed binding/source identities and snapshot state before checking the generation fence; the binding lock also serializes same-binding initial inserts. Blocked and replayed writes release locks via rollback. Existing observation TTL, timestamp, failure and redaction contracts remain unchanged. This does not add a provider recovery signal or authorize runtime activation. Focused tests compile the locking statements with the PostgreSQL dialect and exercise stale/failure ordering; real concurrent PostgreSQL/provider UAT is still required. Different-binding replacement and end-to-end recovery qualification remain under #5229.

## HV-12 consolidated provider lifecycle work (#5229)

The scoped Central Alert Intelligence read adapter distinguishes the last admitted firing case from current committed source evidence. It reuses the exact-binding, five-minute observation reader after historical case provenance and instance authorization qualify. Only a fresh firing entry matching the case's opaque occurrence handle projects firing; absent, stale, failed, disabled, suppressed and unprocessed source observations project unknown, retain the durable case, and never imply recovery or write a case transition. The source-unknown filter and count describe admitted cases, not fleet health. The shared links retain the selected provider and source-state filter. This is the currentness portion of the consolidated #5229 work branch; positive recovery, scoped mutation, delivery and actual PostgreSQL/provider UAT remain separately qualified before activation.

### Audited source-state transitions (#5229)

The existing default-disabled internal admission command may transition a provenance-qualified open case from firing to unknown when a newer, fresh and qualified snapshot cannot verify the occurrence as firing (omitted, suppressed or unprocessed). The original last firing observation is retained; source-state change time and reason fence subsequent changes, and a sanitized case event and audit entry are committed in the same transaction. Only a newer matching firing observation can restore firing. Repeated generations do not duplicate events; scope, source and policy-ineligible suppressed routing remain mandatory. Expired, failed, disabled or otherwise unavailable observations continue to project unknown at read time without writing a case transition. A newer successful qualified empty observation may commit unknown for existing non-closed cases only (see recovery qualification below). No source recovery, closure, workflow mutation, scheduler or delivery is admitted. A positive recovery source remains unqualified: the HV-12 authority explicitly prohibits a new webhook listener, and Alertmanager GET absence or endsAt alone cannot establish recovery. Real provider and PostgreSQL UAT remain required.

### Operator and delivery qualification boundary (#5229)

The existing governed grant writer in `app/access/scoped_grants.py` issues only `secrets_pki.view` grants. Under #724, a read grant is not an independently scoped operator permission; global Intelligence decision authority does not establish that missing grant. Operator actions remain blocked rather than extending the existing read policy by implication. The generic lifecycle helpers reject Secrets & PKI provider-origin cases before changing workflow, silence, recovery or closure state. The generic notification dispatch and transport seams reject non-recommendation origin even if called outside the worker selector; the expired-silence worker also excludes Secrets & PKI provider cases. These guards do not authorize any new action, alter recommendation delivery, or qualify positive recovery. Shared scoped UI distinguishes the missing operator authorization, positive recovery and governed delivery prerequisites. Focused negative regressions extend `tests/intelligence/test_vault_provider_case_workspace.py`; actual PostgreSQL and hosted UAT remain outstanding. A separately qualified action-specific scoped grant lifecycle and opt-in delivery contract are required before enabling operator mutations or notifications.

### Independent operator scope prerequisite (#5229)

The internal Access grant lifecycle now permits an exact-instance grant for the existing `intelligence.decisions.create` permission, with independent approval and revision audit. The separate operator evaluator intersects it with a currently approved exact `secrets_pki.view` instance grant and normalized global roles; neither scope grants the other or any Vault mount permission. This is a backend authorization prerequisite only. Generic case lifecycle and delivery guards remain intact, and no operator mutation, recovery, notification or grant-admin route is enabled. Source-specific command qualification and real PostgreSQL/provider UAT remain outstanding.

### Internal scoped operator command (#5229)

The opt-in internal `apply_vault_provider_operator_action` command reuses the canonical AlertCase fields, AlertCaseEvent and AuditEvent. It requires an exact validated binding, independent approved read/decision instance scope, a fresh firing observation matching the admitted occurrence and generation, and the expected latest case event ID. Binding-first serialization precedes scope, snapshot and case locks. Acknowledge is a one-time open-to-acknowledged transition without delivery reminders; assignment is idempotent and requires a separately eligible recipient (or explicit unassignment); mitigating requires the acknowledged case owner. The command commits workflow and sanitized case/audit evidence together, rolls back on failure and never changes source state, recovery, closure, routing or sends notifications. It accepts no free-text note, provider payload or credential. The existing admission activation remains default-disabled, and there is no HTTP or worker caller. Shared read projection and UI action publication are not implemented by this slice; actual PostgreSQL concurrency, Access review and provider UAT remain required. Focused regression tests extend `tests/intelligence/test_vault_provider_case_admission.py`.

### Shared committed operator workflow projection (#5229)

The existing exact-instance read adapter now admits open, acknowledged and mitigating workflows only when the stored fields and latest operator case event agree and a matching canonical AuditEvent exists for a non-pristine workflow. Unsupported closure/verification and missing or inconsistent operator evidence fail closed; the same guard protects subsequent internal operator actions. Shared Active Alerts uses the existing workflow filter and status tones; ownership is projected only as Assigned/Unassigned, not a user identifier, and detail shows committed acknowledgement and mitigation timestamps. Source unknown remains independent of workflow. No mutation form, HTTP endpoint, notification or new activation is published; access/recipient selector, authenticated command invocation and hosted UAT remain outstanding. Regression coverage extends the existing admission and workspace suites.

### Authenticated scoped operator controls (#5229)

Central case detail now has a separately default-disabled HTTP adapter, requiring both existing admission opt-in and `KAORI_VAULT_PROVIDER_CASE_OPERATOR_WEB_ENABLED=true`. Do not set either for normal operations before independent review and live qualification. GET controls require audited exact read/decision scope, current qualified binding, matching admitted fresh firing generation and latest event. Recipient candidates are bounded to 32 distinct exact-instance decision principals, independently requalified against both grants; only eligible usernames/IDs are shown in the authorized selector. No global user enumeration or recipient notification. The POST endpoint requires authenticated session, three existing RBAC permissions, explicit Flask-WTF CSRF validation, a strict form allowlist and replay precondition; the owning command repeats scope and source checks. HTMX uses a full detail refresh via HX-Redirect and transient operational feedback; ordinary forms use HTTP 303. The generic mutation endpoints remain blocked for provider cases. No runtime settings, grants, source I/O, notification or recovery are activated. Tests added; real HTTP/browser, PostgreSQL concurrency and independent review remain mandatory.

### Explicit recovery qualification and empty observation parity (#5229)

The current Alertmanager GET v2 contract is active-alert observation, not an authoritative recovery ledger. Expired endsAt, missing rows, empty results, inhibition/silence, unprocessed state, provider outage or changed bindings cannot prove recovery. Upstream API and lifecycle references: https://github.com/prometheus/alertmanager/blob/main/api/v2/openapi.yaml and https://prometheus.io/docs/alerting/latest/alerts_api/ . The generic Alertmanager normalizer's legacy endsAt fallback is not a qualified Vault recovery input. Prometheus active-alert list absence alone is likewise insufficient. #2596 prohibits a new webhook listener; no transport or provider mutation is authorized.

A current successful exact-binding empty generation now plans retain_unverified for existing non-closed cases, using the same source lock, scoped admission, monotonic generation, atomic event/audit, and suppressed routing as non-empty omissions. Empty first observations create no cases, closed cases are not reopened, and collisions are checked for existing as well as observed keys. Stale, failed, disabled and ambiguous sources remain non-mutating; source currentness projects Unknown. Operator workflow, ownership and original last firing time remain unchanged. Fresh exact firing may restore Firing, not imply prior resolution. No positive recovery or verification_pending/closed transition is admitted.

Positive recovery remains an explicit capability gap. Before implementation, qualify an existing provider-owned authoritative positive recovery record with exact originating rule/evaluator and source identity, occurrence continuity to the admitted opaque handle, timestamp/generation monotonicity, producer health and completeness, HA/dedup semantics, trusted committed job provenance, scoped authorization and redacted evidence. An operator acknowledgement, health probe, absent time series, expiry or generic normalized resolved label is not a substitute. Require a real disposable provider test proving firing, positive recovery and outage/expiry negatives; then separately qualify canonical verification/closure and delivery. No synthetic recovery writer, extra webhook, new permission, schema or runtime enablement in this slice.

### Governed firing delivery qualification preflight (#5229)

The canonical outbound catalog currently does not admit secrets_pki. The existing AlertRoutingPolicy writer only supports recommendation-origin Kubernetes/Object Storage/Registry. Existing NotificationDelivery deduplicates per channel/event key; its recovery worker rechecks channel/transport but not Vault source/currentness or exact instance target authority. The committed claim precedes network transport and remains at-least-once, not exactly-once. No existing scoped recipient/target authorization was demonstrated by successful Test Delivery alone.

A new internal, non-dispatching preflight reviews an explicitly selected existing policy/channel against normalized integrations.manage plus independent exact read/decision grants, fresh exact admitted firing generation, canonical workflow and provenance. Proposed candidate shape (not an enabled policy writer): dedicated secrets_pki/provider_alert policy, exact vault_instance and source_binding_id matchers, single channel, supported severity, send_resolved=false; dedicated active configured successfully tested firing channel with severity threshold. Acknowledged/mitigating cases are suppressed; any previous firing journal attempt on that channel requires review independent of routing policy/bucket. No destination, credentials, source handle, labels or provider payload returned; scoped result audit is committed before returning candidate qualification. No success branch: catalog absence blocks, and even hypothetical catalog admission cannot substitute approved recipient/target authority. Generic channel matcher and generic recovery explicitly deny secrets_pki pending source-aware transport and retry admission. No new transport, schema, catalog entry, policy writer, schedule, notification, or runtime activation. Before enabling any first firing delivery, approve target governance, atomic claim/revalidation and bounded redacted content under existing transport; independently qualify replay, destination change, concurrent dispatch, repeat/ack and actual disposable channel UAT. Explicit resolved delivery remains blocked by positive recovery authority.

### Consolidated review hardening (#5229)

Observation admission revalidates the binding under lock, refreshes and locks existing AlertCase rows, and rejects unqualified operator workflow instead of advancing source evidence over corrupt state. Exact-instance policy evaluation refreshes the locked policy and revision rather than trusting an ORM-cached revision pointer. Operator event qualification checks the referenced previous event belongs to the same case and that the canonical audit includes matching workflow and ownership. Central detail locks the read case and derives the expected event from that view; controls are omitted if the independent post-read authorization/currentness transaction sees a different event or the rendered source is not firing. No additional production capability or authorization is enabled. These changes are branch-only pending Developer Check, independent review and real UAT.

### Dev Container review — operator application boundary (#5229)

The HTTP adapter performs feature gating, authenticated actor extraction, CSRF/form validation and response selection only. Operator control qualification, exact active Alert Source selection, scope/recipient locks, committed observation checks and atomic read audit belong to vault_operator_service. The existing operator command requalifies the binding and scope under lock before mutation. Other integration types do not compete with the exact Alert Source selector; ambiguous active Alert Sources still fail closed. No feature flags, source recovery or delivery authority are changed. Local application-package and quality gates must pass before staging admission.

### Local review usability (#5229)

The central provider overview now renders only scoped admitted-case counts (active, critical severity, fresh firing, unknown); it does not substitute counts for source health. Lifecycle readiness separates observation, conditional operator workflow, unavailable positive recovery and suppressed delivery. The scoped detail shows a generic controls-unavailable state rather than silently hiding the action section; the legacy read-only detail links to the exact central context. Unavailable owner selection cannot submit an implicit unassign. A qualified first empty observation with no actionable prior case is a successful no-op, not recovery or source outage. No runtime capability is enabled by these changes.

### Local Dev Container case reconciliation (#5229 / #2227)

The central Alert Intelligence Active queue offers **Reconcile Cases (Local
UAT)** only for an authorized Vault instance when explicit APP_ENV=development
matches application configuration and both existing admission/operator web
opt-ins are true. The authenticated actor must have all four explicit role
permissions (intelligence.view, intelligence.decisions.create,
secrets_pki.view, secrets_pki.sync) and independently approved exact-instance
read and decision grants. The POST accepts only CSRF and the selected instance,
resolves the unique active Alert Source and rechecks exact identity, locked
role membership, grants and committed source generation in the owning
admission transaction. Existing audit, capacity and deduplication rules
remain authoritative. Reconciling the queue is not a provider refresh.
There is no provider call, notification delivery, recovery inference or
automatic scheduler. A production config cannot enable this local route.
Only use a disposable Dev Container database and approved source fixtures;
leave both opt-ins disabled elsewhere. Local functional/visual validation
and official staging admission are pending.

### Scoped incident evidence and lifecycle review (#5229)

The exact-instance audited case detail now projects a bounded latest 25 recorded lifecycle events (five recent, up to twenty expandable) through the shared incident timeline. Only allowlisted event types and metadata shapes qualify, with fixed redacted labels and descriptions; no persisted summary, actor identity, opaque handle or provider payload is exposed. A malformed selected event produces unavailable timeline evidence, not a misleading empty successful history. The projection is not proof of each historical audit or an unbounded audit export. Committed observation state (fresh/expired/unobserved/unavailable) is distinct from current firing and admitted workflow. The shared delivery ledger explicitly reports Not Qualified, not zero attempts. Delivery preflight reuses the same current firing predicate as operator controls and mutation. No recovery, closure, notification transport or policy activation is added by this view.

### Exact-instance runtime context (#5229 / #2596)

Case detail includes the most recent committed IntegrationRuntimeObservation for the exact canonical Vault integration ID, separately from the Alertmanager observation. Only fixed health/readiness labels, bounded recorded score and observation timestamp are projected under the existing audited case read. A foreign provider/adapter, incoherent timestamps or unsupported latest record produces unavailable context; no historical healthy fallback. No credential-bearing Vault model, runtime diagnostics, payload, endpoint, namespace, mount or fleet aggregate is read. This is historical supporting context, not a current-health guarantee, inferred cause, positive recovery, or permission to disclose mount/consumer evidence. Other contextual evidence requires its own qualified join and authorization. No mutation or notification is enabled.

### Consolidated source and evidence integrity batch (#5229 / #2595)

Provider observation generation is now ordered by the initiation of the bounded read rather than network completion; delayed responses/failures cannot supersede a newer committed generation, and a read exceeding the existing freshness window is unavailable. Snapshot reads refresh ORM state and require the exact versioned payload key set. All internal case admission paths lock the explicit normalized role permission rows before evaluating the exact grant. An invalid admitted source state blocks the candidate plan rather than being relabeled unverified. PKI validity population evaluation additionally requires ordered observation/commit timestamps and rejects duplicate selected collection-state identities. These are implementation changes only; actual PostgreSQL concurrency, worker/provider and consolidated UAT remain pending. The positive recovery source and authorized notification destination contract remain separate unresolved prerequisites; no transport or recovery is enabled.


### Independent signed authority contract (#5252 / #5253)

Approved direction: use deployment-owned, separately pinned Ed25519 evidence
following the existing issuer authority pattern, not a new webhook listener
or alert engine. The fixed `/run/kaori/vault-alert-authority` directory must
be root-owned, non-writable by application principals, and mounted read-only.
No private signing key is part of KAORI. Missing files, bad signatures,
unexpected fields, expired receipts or revision mismatch fail closed.

Recovery exporter must be provider-owned and attest explicit resolution of
the exact Alertmanager occurrence, from authoritative rule/evaluator event
history. The canonical JSON envelope contains only payload and signature.
`recovery-<binding_id>.pub` is the independently pinned hex Ed25519 public
key; the matching JSON payload schema is `kaori.vault.alert_recovery.v1`,
state active, exact binding/instance/source IDs, binding/source updated_at
UTC ISO timestamps, issued_at/expires_at UTC, complete=true, and a bounded
entries list of fingerprint, starts_at, resolved_at, opaque rule_ref (64
lowercase hex), state=resolved. The signer must prove the occurrence
continuity and completeness; active GET, silence, outage and missing alerts
are not acceptable producer inputs. The existing manual observation worker
alone derives the same HMAC occurrence handles and commits a separate,
short-lived AlertSignalSnapshot linked to the active GET generation. No raw
fingerprint, rule identifier, signed payload or provider data is persisted.
No recovery producer/exporter has yet been provisioned or validated.

Destination approval is independently pinned per exact binding/policy/channel
(`delivery-<binding_id>-<policy_id>-<channel_id>.pub/.json`). Schema
`kaori.vault.alert_destination.v1` binds exact case public ID, canonical
instance/binding, policy/channel IDs, policy/channel updated_at, channel
last_tested_at, purpose alert_ops.firing, maker/checker IDs and signed validity.
Checker must differ from the acting maker and hold explicit normalized
roles.manage, users.manage, integrations.manage. Existing exact operator
scope and channel eligibility are still mandatory. Any channel/policy
update invalidates this conservative one-attempt receipt. No secret values,
transport config, credentials or destination are persisted in authority
evidence. Signed receipt qualification is not yet transport authorization;
catalog, claim and replay admission remain gated. No receipt generation,
automatic source mutation, new channel transport or production activation.

### Local positive recovery and verification transaction (#5252)

The existing local-only operator POST now supports explicit Admit Provider Recovery and Verify and Close, never from request-supplied evidence. Binding, normalized permissions, exact operator scope, current active snapshot, same-generation signed recovery snapshot and canonical case are locked and rechecked. Positive receipt resolution must be later than the last admitted firing, with no matching occurrence in the current source response (including suppressed/unprocessed). A signed receipt is mandatory; absence is only a conflict check, not evidence. Recovery records the actual resolved timestamp and enters verification_pending. Closure requires a subsequent fresh source generation after verification started, the same explicit resolution timestamp and a different independently scoped operator. Canonical AlertCaseEvent/AuditEvent commit atomically, with opaque receipt reference, generation, previous event and approved policy revision. Read qualification rejects incomplete or forged recovery/closure records, and same-occurrence reappearance blocks reconciliation. Resolved tab shares the scoped registry. No automatic mutation, provider operation, notification, postmortem editing or live evidence qualification. Existing local feature gates remain mandatory. A real provider exporter and independent signed receipts must be provisioned and accepted before this path can work.


### Explicit local firing claim and restricted retry (#5253)

The outbound catalog admits Secrets & PKI firing configuration only; generic
notification matching and automatic replay continue to deny this domain.
The local routing candidate writer uses the canonical AlertRoutingPolicy,
one exact Vault binding and dedicated validated channel, with no generic
broadcast or automatic routing. Candidate creation is not disclosure
approval. An authenticated exact-instance operator with integrations.manage
must obtain an independent, current signed destination receipt before an
explicit Send Approved Firing action. Existing local development opt-ins
are mandatory. Source freshness, workflow, roles, grant, binding, policy,
channel, receipt and prior journal requalify under locks. A fixed redacted
message contains no provider labels, identities, paths, URLs or custom
templates. Existing NotificationDelivery reservation and encrypted transport
replay envelope commit before transport. A second locked qualification
checks the same receipt and claim before invoking the existing sender; only
sanitized provider outcome is recorded. One occurrence has at most one first
claim across destinations. Uncertain or queued outcomes require review and
cannot be automatically replayed. Explicit retry is possible only for the
same journal and transport, a new approval after an explicitly classified
provider rejection and a persisted retry deadline (Slack HTTP 429 with a
valid Retry-After only), within the existing attempt bounds. Other failures
are ambiguous for retry purposes. No exactly-once transport guarantee,
repeat broadcast, resolved delivery or provider mutation. The scoped
read model projects only qualified journal status and attempt count, not
destination, channel configuration or provider response. Actual source
and destination provisioning and local functional, security and concurrency
verification remain outstanding; no production activation or CI admission.

### Consolidated review qualifications (#5252 / #5253)

The dedicated destination receipt additionally binds the current canonical Alert Source ID and binding/source revisions. The independent checker must hold an approved exact-instance read grant in addition to normalized administration permissions. A dedicated firing-only Secrets & PKI channel is enforced in the form validator. Recovery verification requires the recovery event to remain the latest canonical case event. The local runbook records the genuine exporter, checker and disposable-channel prerequisites; these are not simulated by fixtures. No changes to deployment, provider configuration or secret-bearing data were executed.

### Generation and receipt revocation hardening (#5229 / #5252)

Active observation payload v2 pins canonical binding and source updated_at revisions. The trusted manual worker captures those revisions before I/O, and the locked commit/failure paths reject responses from a changed configuration. Consumers reject v1 snapshots and mismatched revisions; run a new qualified observation after updating/revalidating a binding. No migration or fallback is needed because the snapshot is disposable evidence, not durable case history. Recovery payload v2 additionally records the signed receipt issue time, rejects resolution after receipt issuance, requalifies the active generation, and re-reads the independent signature and exact digest before mutation. Revoked/replaced receipts fail closed immediately. Independent verification now requires a different receipt issued after verification started, not merely reuse of the original signed record on a newer GET. Provider exporter and real signed receipts remain external prerequisites; no synthetic generation.

### Hot delivery evidence integrity (#5253)

Preflight and first claim now check the journal across all channels and existing claim audit, not merely the requested channel. A missing journal with prior claim evidence blocks another first attempt. Preflight locks explicit role permissions and candidate policy/channel; signed revisions must all exist. The claim and canonical sanitized outcome now each have matching transactional audit evidence. Retry requires a matching audited definitive rejection, not only a payload flag. The scoped ledger refuses an unaudited sent state and presents claims lacking confirmed outcomes as queued/review-required. Existing notification and audit retention remain archive-only; durable cleanup stays blocked under #2868. Canonical binding invalidation remains the source-configuration serialization boundary, avoiding reverse source-row lock ordering. No provider I/O or testing was performed by this source change.
