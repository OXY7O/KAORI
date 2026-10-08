# Domain Evidence and Central Intelligence Ownership Standard

Authority: #900, derived from #561.

This standard defines the reusable ownership boundary between KAORI operational domains, the central Intelligence domain, and Automation Control.

## Governing model

```text
Authoritative Domain
├── provider/source evidence
├── normalized committed state
├── domain lifecycle
├── domain analytics
├── forecasts / derived facts
└── domain operational context
        │
        ▼
KAORI Intelligence
├── Rule Catalog
├── Recommendations
├── finding lifecycle
├── Accepted Risk / exceptions
├── Alert Intelligence
└── decision semantics
        │
        ▼
Automation Control
└── governed execution / verification
```

The external provider remains authoritative for provider-native execution and state.

KAORI domains own normalized facts, lifecycle, analytics, correlation, and committed evidence. Intelligence owns recommendation semantics. Automation Control owns governed execution orchestration.

## Domain ownership

A domain owns facts and derived operational analytics that are specific to that domain.

Examples:

- Artifact Registry: registry inventory, project quota/capacity, artifact growth, forecast, vulnerability/signature/SBOM evidence, retention/immutability/replication posture, runtime-artifact correlation.
- Object Storage: system/bucket inventory, capacity, growth, forecast, policy evidence.
- Kubernetes: cluster/runtime inventory, capacity, governance, deployment/runtime evidence.
- Secrets & PKI: Secret, Certificate, Issuer, Lease, expiration, consumer/materialization evidence.
- Source Control: repository, branch, protection, change, governance, delivery evidence.
- FinOps: cost, allocation, budget, forecast, cost anomaly evidence.
- Backup & Recovery: protection, backup, restore-test, RPO/RTO, recovery-readiness evidence.
- Network Operations: connectivity, flow, DNS, network-policy, dependency evidence.

A domain may calculate:

- current posture;
- trend;
- growth;
- utilization/headroom;
- forecast;
- anomaly;
- correlation;
- confidence/freshness;
- evidence quality.

These remain domain facts or derived analytics. They are not automatically Recommendations.

## Intelligence ownership

KAORI Intelligence is the only canonical owner for:

- Rule Catalog;
- recommendation evaluation;
- recommendation persistence and lifecycle;
- finding identity;
- Accepted Risk / rule exceptions;
- recommendation decision semantics;
- Alert Intelligence escalation;
- recommendation-driven governance state.

Do not introduce parallel domain-local recommendation engines, rule catalogs, accepted-risk workflows, or recommendation lifecycle tables.

Analytics pages consume central Intelligence rather than embedding page-specific recommendation logic.

## Evidence-to-recommendation flow

Example:

```text
Artifact Registry fact
  quota utilization = 84%

Artifact Registry analytics
  growth = +5.8 GiB/day
  projected exhaustion = 18 days

Intelligence Rule Catalog
  registry.capacity.quota_exhaustion

Central Recommendation
  review quota / retention / artifact growth
```

The domain produces the evidence. Intelligence evaluates whether that evidence satisfies a rule and owns the resulting recommendation.

## Rule namespace and provider coverage

Rules use canonical domain-oriented namespaces where possible:

```text
registry.*
object_storage.*
kubernetes.*
secrets_pki.*
source_control.*
finops.*
backup_recovery.*
network.*
```

Provider identity is normally evidence or coverage metadata.

For example:

```text
Rule
  registry.capacity.quota_exhaustion

Provider coverage
  Harbor          qualified
  AWS ECR         planned
  Azure ACR       planned
```

Do not create a vendor rule namespace merely because the first implementation uses one provider.

A provider-specific rule is justified only when the condition is genuinely provider-native and cannot be represented by the canonical domain semantics.

## Domain UI rule

Domain workspaces may show:

- factual posture;
- analytics;
- recommendation count;
- recommendation preview;
- recommendation priority/status projection;
- a link to the canonical Intelligence recommendation.

They must not own:

- a second Recommendations workspace;
- independent acknowledgement state;
- independent recommendation resolution;
- independent Accepted Risk;
- independent recommendation decision/approval;
- independent automation lifecycle.

Canonical operator surfaces remain:

```text
Intelligence → Recommendations
Intelligence → Rule Catalog
Intelligence → Alert Intelligence
Intelligence → Automation Control
```

Domain drill-down and Intelligence drill-back should preserve domain, asset, source evidence, and provenance.

## Alert Intelligence boundary

A domain fact or Recommendation does not automatically become an operational alert.

Alert Intelligence escalation uses central policy and relevant context such as:

- severity/priority;
- runtime exposure;
- affected assets/services;
- production sensitivity;
- urgency/time-to-impact;
- fix/remediation availability;
- evidence freshness;
- Accepted Risk / exception state;
- cross-domain correlation.

Example:

```text
Critical registry vulnerability
+ artifact running in production
+ meaningful blast radius
+ no active accepted-risk scope
→ eligible for central operational escalation
```

Raw CVEs, quota thresholds, unsigned artifacts, forecast values, or other domain facts must not bypass this central escalation boundary.

## Security Posture boundary

Security Posture aggregates cross-domain security findings.

```text
Artifact Registry
  = source-domain security evidence

Security Posture
  = cross-domain security aggregation

Intelligence
  = recommendation/rule/decision semantics
```

Security Posture must not become a second recommendation engine.

## Automation Control boundary

Domains do not execute remediation merely because they discovered an issue.

The canonical governed execution path is:

```text
Domain evidence
→ Intelligence recommendation/finding
→ decision / approval where required
→ Automation Control
→ validated runbook / binding
→ authoritative provider executes
→ KAORI verifies
→ committed evidence / audit
```

Automation Control is the cross-domain orchestration/governance bridge. It does not replace provider authority or domain-specific security/RBAC requirements.

Examples of future actions that must use this path when driven from Intelligence include:

- registry quota/retention/replication operations;
- Kubernetes operational actions;
- object-storage remediation;
- Vault/Secrets operations;
- network-policy or infrastructure changes.

Direct Recommendation → provider mutation is not allowed.

## Provider and source independence

Recommendation semantics are not tied to one telemetry or provider source.

A domain may produce evidence from:

- provider API;
- committed inventory;
- Metrics Source;
- Alertmanager;
- webhook/event evidence;
- worker-materialized analytics;
- cross-domain correlations.

The Intelligence rule contract consumes normalized committed evidence and records provenance.

Do not make one external source, such as Prometheus, Harbor, MinIO, or Alertmanager, the schema owner for Intelligence.

## Architecture review checklist

Every new domain or major capability must answer:

1. What provider/source evidence does the domain own?
2. What normalized committed state does the domain own?
3. Which lifecycle states are domain-specific?
4. Which analytics, forecasts, anomalies, and correlations remain domain-owned?
5. Which evidence is eligible as input to Intelligence?
6. Which canonical Rule Catalog namespace evaluates it?
7. Does the design duplicate Recommendation, Rule Catalog, Accepted Risk, or decision lifecycle?
8. What conditions qualify a Recommendation for Alert Intelligence escalation?
9. Could a Recommendation lead to a provider mutation?
10. If yes, which Automation Control runbook/binding and provider boundary executes it?
11. Does domain UI only project central Recommendation state rather than own another lifecycle?
12. Are provider identity and evidence provenance retained without making the provider the canonical rule/domain identity?

A design that creates a second recommendation engine, accepted-risk model, or automation-control path fails this boundary unless a separately approved architecture authority explicitly justifies the exception.

## Review and delivery

This standard is an architecture and implementation gate.

Future implementation issues should reference it when they introduce:

- new domain analytics;
- new recommendation inputs;
- new Rule Catalog definitions;
- new Alert Intelligence escalation;
- new Automation Control actions.

For existing work, Registry / Artifact Registry #558 and #899 are the first explicit consumers of this standard.

The standard changes ownership and implementation boundaries only. It does not enable new provider mutation or bypass existing Developer Check, Full Admission, staging/UAT, security, RBAC, or human-acceptance requirements.
