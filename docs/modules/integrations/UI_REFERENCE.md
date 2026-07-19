# Integrations UI Reference

## Scope

This document owns domain-specific UI behavior for the Integrations landing page. Global visual rules remain in `docs/design/KAORI_DESIGN_SYSTEM.md`, while the hero contract remains in `docs/design/components/HERO.md`.

## Information hierarchy

The Integrations landing page follows this fixed sequence:

1. Standard Hero
2. Provider Catalog
3. Operational Overview
4. Integration Domain Coverage

The hero explains the purpose of the integration platform. It must not duplicate provider navigation already represented by the Provider Catalog.

## Hero contract

The Integrations hero uses no more than two visible actions:

- `Browse Providers` moves the user to the Provider Catalog.
- `Refresh Status` refreshes only the Operational Overview through HTMX.

Provider-specific navigation such as Kubernetes, Prometheus, and Alertmanager must not appear as separate hero buttons.

Hero metadata is limited to three items:

- Available provider count.
- Configured target count.
- Discovery mode.

Runtime health, readiness, attention counts, and capability posture belong in the Operational Overview below the hero.

## Provider Catalog

The Provider Catalog is the primary entry point for provider workspaces. Available providers expose a `Manage` action. Planned providers remain visible to communicate roadmap categories but do not expose unfinished configuration workflows.

Provider cards may show provider category, availability, configured instance count, and a concise purpose statement. They must not become mini dashboards.

## Operational Overview

Operational Overview presents persisted runtime evidence, filters, and the paginated integration registry. The summary metrics use a compact strip rather than five independent dashboard cards. Long provider error details are visually truncated in the table and remain available through the row title or provider detail workspace.

## Scalability rule

Adding a provider must extend the Provider Catalog and provider-neutral runtime data. It must not require redesigning the hero or adding another hero action.
