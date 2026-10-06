# Registry Provider-Agnostic Extension Gate

This document is the implementation review gate for the Registry / Artifact Registry foundation derived from #558, #884, and #895.

Harbor is the first production-qualified Registry provider. The foundation is accepted only when Harbor proves the provider contract without making the canonical Registry domain, persistence, consumer logic, or Artifact Registry UI Harbor-specific.

## Gate Intent

A future Registry provider should extend KAORI through provider definitions, adapters/collectors, normalization, and capability qualification.

It must not require a redesign of the Registry product.

Reference future providers include:

- AWS ECR;
- Azure Container Registry;
- Google Artifact Registry;
- GitHub Container Registry;
- Docker Hub / OCI Distribution-compatible registries;
- other OCI Registry providers.

These providers do not need production implementations for the Harbor delivery to pass this gate.

## Stable Canonical Core

The following identity hierarchy is provider-neutral and must remain stable:

```text
Registry Instance
→ Project / Namespace
→ Repository
→ Artifact Digest
→ Tag(s)
```

Digest is the preferred immutable artifact identity. Tags remain mutable aliases.

Canonical persistence and domain contracts use Registry vocabulary such as:

- RegistryCollectionState;
- RegistryProject;
- RegistryRepository;
- RegistryArtifact;
- RegistryTag;
- provider-neutral security/governance/correlation models.

Provider-native identifiers and fields may be retained as provenance or provider metadata, but they must not redefine canonical identity.

## Stable Product Information Architecture

The Artifact Registry product remains provider-neutral:

```text
Artifact Registry
├── Overview
├── Inventory
│   ├── Projects
│   ├── Repositories
│   └── Artifacts
├── Security
├── Governance
└── Analytics
```

A provider must not introduce a separate Harbor/ECR/ACR/GAR product menu.

Provider identity is a source/filter/context dimension. Capability state determines what each provider can contribute.

## Core and Optional Capability Model

Provider behavior is expressed through semantic Registry capabilities rather than provider product names.

Core examples:

- provider identity/readiness;
- project/namespace discovery where the provider model has an equivalent scope;
- repository discovery;
- artifact/digest discovery;
- tag discovery;
- committed collection/freshness.

Qualified optional examples:

- vulnerability evidence;
- signature evidence;
- SBOM evidence;
- retention/lifecycle governance;
- immutability;
- replication;
- webhook/event reconciliation;
- operational metrics;
- provider audit/event evidence;
- proxy-cache/provider-specific extensions.

Shared UI must represent optional capability state explicitly:

```text
Supported + observed
Supported + unavailable
Unsupported by provider
Not yet collected / not yet qualified
```

An unavailable or unsupported optional capability must not invalidate unrelated Registry capabilities.

## Provider Registration Gate

Shared Registry taxonomy, navigation, readiness, and Integration Kernel code must not encode Harbor as the only possible provider.

Pass criteria:

- Registry remains the integration capability/domain.
- Harbor is one provider registration beneath Registry.
- Multiple provider instances continue to use IntegrationInstance.
- Provider-specific auth/API/runtime logic remains under the provider/adapter boundary.
- Compatibility and capability evidence is definition-driven.
- A synthetic/test second Registry provider can register without changes to Harbor provider code or canonical Registry taxonomy.

The target extension shape is:

```text
Registry Integration Type
        ↓
Provider Registry
   ├── Harbor
   ├── future ECR
   ├── future ACR
   └── future provider
```

Future provider entries may be represented as planned lifecycle definitions without claiming implementation readiness.

## Inventory Collector Gate

Generic Artifact Registry collection must resolve the provider implementation through a collector/provider registry or an equivalent Integration Kernel registration mechanism.

Target:

```text
IntegrationInstance
        ↓
provider_key
        ↓
Registry Collector Registry
        ↓
qualified provider collector
        ↓
RegistryInventoryEvidence
        ↓
committed Registry models
```

A temporary Harbor-only branch during first implementation is acceptable, but foundation lock fails if generic collection evolves into:

```text
if harbor
elif ecr
elif acr
elif gar
...
```

Provider selection belongs to registration/dispatch, not accumulating business-logic conditionals.

## Consumer Isolation Gate

Downstream consumers must depend on canonical Registry evidence, not Harbor implementation details.

The following must remain provider-independent:

- Artifact Registry routes/navigation;
- Kubernetes image/artifact correlation;
- digest-oriented runtime blast-radius logic;
- security presentation;
- governance presentation;
- Metrics Source / IntegrationBinding architecture;
- Intelligence/Recommendation consumers;
- reporting/evidence consumers.

For example:

```text
Kubernetes image reference
→ normalized repository/digest
→ RegistryArtifact
→ runtime binding
```

must not require the consumer to know whether RegistryArtifact originated from Harbor, ECR, ACR, GAR, or another provider.

## Observability Gate

Registry operational telemetry remains source/asset oriented:

```text
Registry provider telemetry
→ external telemetry backend
→ KAORI Metrics Source
→ IntegrationBinding
→ Registry managed asset
```

Harbor-specific Prometheus transport must not be embedded into the canonical Registry domain.

A future provider may use a different telemetry backend or expose no qualified operational metrics.

## UI Drift Gate

Pass criteria:

- no provider-specific top-level Artifact Registry navigation;
- no separate canonical Harbor inventory/security/governance page family;
- provider selector/filter can combine evidence from multiple Registry providers;
- shared pages show factual capability gaps;
- unsupported capabilities produce a standard state rather than disappearing through provider-name template branching;
- provider-native details may appear as contextual evidence without changing the page identity.

## Automated Contract Evidence

Before the foundation is treated as locked, focused automated tests should prove at least:

1. a synthetic/test second provider can be registered beneath Registry;
2. shared provider lookup/dispatch does not require Harbor-specific branching;
3. a second provider collector can normalize inventory into the same Registry models/contracts;
4. canonical persistence does not require Harbor fields;
5. common Artifact Registry routes/presentation accept provider-neutral evidence;
6. unsupported optional capability state does not block unrelated views;
7. digest-based Kubernetes correlation remains provider-independent;
8. no provider-specific source-to-source binding table is required.

A real ECR/ACR/GAR implementation is not required to execute this contract test. A deterministic test provider/fixture is sufficient to prove the architecture boundary.

## Review Checklist

Use this checklist during consolidated local review and again before normal admission:

- [ ] Registry taxonomy is provider-neutral.
- [ ] Harbor is first provider, not domain identity.
- [ ] Provider matrix/definition structure supports planned future Registry providers.
- [ ] IntegrationInstance remains the canonical provider-instance identity.
- [ ] No generic Registry runtime path assumes Harbor is the only provider.
- [ ] Inventory collector dispatch uses registry/registration semantics or has an explicit blocking gap before foundation lock.
- [ ] Canonical models remain Registry-named.
- [ ] Provider-native metadata is isolated from canonical schema.
- [ ] Artifact Registry routes/navigation remain provider-neutral.
- [ ] Capability gaps use explicit supported/unavailable/unsupported/not-qualified states.
- [ ] Security, governance, correlation, and observability consumers remain provider-neutral.
- [ ] Synthetic second-provider contract tests pass.
- [ ] No large domain/UI refactor would be required to add the next Registry provider.

## Gate Disposition

During review, record one disposition:

- **PASS** — extension contract is implemented and protected by tests;
- **GAP** — architecture is correct but an implementation dependency still makes the second-provider path provider-specific;
- **DEFERRED** — only when the gap is explicitly bounded in a follow-up issue and does not require replacing canonical Registry/domain/UI contracts.

A Harbor implementation that works functionally but fails this extension gate is not considered a fully locked Registry foundation.
