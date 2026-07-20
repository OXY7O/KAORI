# Integrations UI Reference

## Scope

This document owns domain-specific UI behavior for the Integrations landing page. Global visual rules remain in `docs/design/KAORI_DESIGN_SYSTEM.md`, while the hero contract remains in `docs/design/components/HERO.md`.

## Information Hierarchy

The Integrations landing page follows this fixed sequence:

1. Standard Hero
2. Provider Catalog
3. Runtime Overview
4. Integration Domain Coverage

The hero explains the purpose of the Integrations domain. It must not duplicate provider navigation already represented by the Provider Catalog.

## Hero Contract

The Integrations hero uses no more than two visible actions:

- `Browse Providers` moves the user to the Provider Catalog.
- `Refresh Status` refreshes only the Runtime Overview through HTMX.

Provider-specific navigation such as Kubernetes, Prometheus, and Alertmanager must not appear as separate hero buttons.

Hero metadata is limited to three items:

- Available provider count.
- Configured target count.
- Discovery mode.

Runtime health, readiness, attention counts, and capability posture belong in the Runtime Overview below the hero.

## Provider Catalog

The Provider Catalog is the primary entry point for provider workspaces. Available providers expose a `Manage` action. Planned providers remain visible to communicate roadmap categories but do not expose unfinished configuration workflows.

Provider cards may show provider category, availability, configured instance count, and a concise purpose statement. They must not become mini dashboards.

Configured counts are provider-native:

- Kubernetes counts persisted Kubernetes connections.
- Prometheus counts registered Prometheus or Thanos instances with an endpoint.
- Alertmanager counts registered Alertmanager instances with an endpoint.

A Prometheus or Alertmanager instance does not require a Kubernetes cluster binding to appear in the catalog count.

## Runtime Overview

Runtime Overview presents the latest persisted runtime state for every registered provider target that implements the shared runtime contract. It is diagnostic rather than a second configuration surface.

The summary metrics use a compact strip rather than independent dashboard cards. Long provider error details remain secondary to instance identity and status. Configuration and remediation stay in the provider detail workspace.

Runtime rows use explicit provider-to-route mapping:

- Kubernetes → Kubernetes integration detail.
- Prometheus / Thanos → Prometheus instance detail.
- Alertmanager → Alertmanager instance detail.

Templates must never call `url_for()` with a dynamic endpoint supplied by a runtime row. An incomplete or unknown row renders an unavailable action instead of breaking the landing page.

## Empty-State Contract

The landing page is valid when zero integrations exist.

With no registered integration:

- the hero renders with zero configured targets;
- the Provider Catalog remains available;
- Runtime Overview renders `No Runtime Targets Yet` inside its owning surface;
- filters, runtime table, and pagination controls are omitted until a target exists;
- the zero-result summary remains visible as `Showing 0–0 of 0 integration targets`;
- Integration Domain Coverage renders zero values normally.

When targets exist but filters return no rows, the table remains visible and renders `No Runtime Targets Match These Filters` with a reset instruction.

An empty provider inventory is a normal product state, not an error condition.

## Dependency Boundary

The landing page reads persisted KAORI records only. Rendering it must not require:

- live Kubernetes, Prometheus, Thanos, or Alertmanager connectivity;
- provider validation or capability discovery;
- a Kubernetes cluster for a Prometheus or Alertmanager instance;
- a primary binding;
- a provider resolver decision;
- runtime observations to exist.

Each provider inventory contributes independently. The absence of one provider must not suppress or invalidate another provider.

The application database schema and registered KAORI routes remain deployment prerequisites. Missing migrations are deployment errors and must not be disguised as an empty integration state.

## Integration Domain Coverage

Coverage mirrors the provider catalog categories:

- Compute & Infrastructure.
- Observability.
- Storage.
- Security.

Kubernetes contributes to Compute & Infrastructure. Prometheus and Alertmanager contribute to Observability. Planned categories remain visible with zero configured and ready targets.

## Scalability Rule

Adding a provider must extend the Provider Catalog, provider-native counts, and provider-neutral runtime data. It must not require redesigning the hero, adding another hero action, or introducing a mandatory dependency on another provider.
