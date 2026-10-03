# KAORI Provider Prerequisite Blocking Standard v1.0

**Status:** Locked shared provider-setup contract  
**Implementation authority:** #894  
**Related:** #198, #206, #470, #748, #750, #774, #884

## Purpose

Provider-backed KAORI workspaces must not invent a different setup experience for every domain.
A missing provider is one state with one structural grammar.

The canonical provider-absent composition is:

```text
Integrated Workspace Tabs when peer routes exist
↓
Stable Hero identity + persistent metadata roles
  right: Blocked / Setup Required provider context
↓
Canonical Provider Setup Blocker
  status + reason + ordered setup steps + one integration-management action
↓
normal operational content is not rendered
```

## State model

### Provider absent

- Level-3 route navigation remains visible.
- Hero eyebrow, H1, description, and metadata roles remain stable.
- Hero-right context communicates Blocked / Setup Required.
- The Hero-right context does not duplicate the full setup CTA.
- The below-Hero blocker owns the primary Integrations action.
- Normal operational content is terminally hidden.

### Provider registered but degraded, unavailable, or validation-required

This is not a setup-absent state.

- Navigation remains visible.
- Committed KAORI evidence remains readable where the domain owns committed state.
- Hero/context communicates degraded or restricted provider operations.
- Provider-backed actions remain fail-closed.
- A remediation action may be exposed where no duplicate below-Hero setup action exists.

## Shared ownership

- `components/page_hero.html` — Hero profile/state authority.
- `components/provider_prerequisite/_hero_context.html` — provider-neutral blocked Hero-right context.
- `components/provider_prerequisite/_setup_blocker.html` — provider-neutral mapping into the canonical blocked-state renderer.
- `components/states/_blocked_state.html` — visual blocker geometry and action/permission behavior.
- `components/workspace_tabs.html` — route-level Integrated Workspace Tabs.
- `components/dependencies/_blocker.html` — secondary dependency path after provider setup exists.

Domain wrappers may provide nouns, icons, routes, permissions, evidence labels, and steps. They must not own a new geometry.

## Analytics

Analytics uses the provider-prerequisite grammar only for the first provider/source prerequisite.

After a provider is registered, missing committed inventory, metrics, alerts, history, or analytics snapshots remain secondary dependencies and continue through the shared dependency blocker.

```text
provider absent
→ Provider Prerequisite Blocker

provider present
→ analytics-specific dependency missing
→ Dependency Blocker
```

## Metadata

Blocked state does not replace the normal metadata vocabulary with setup labels.

Metadata roles remain stable across Normal / Blocked / Degraded. When evidence is unavailable, the value must say so explicitly rather than inventing a healthy observation.

## Action role

The primary provider-setup action routes to the canonical Integrations destination.

Examples:

- Kubernetes → **Open Cluster Integrations**
- Object Storage → **Open Storage Integrations**
- Registry → **Open Registry Integrations**

Do not place the same full setup action in both the Hero-right context and the below-Hero setup blocker.

## Current consumers

- Kubernetes Operations Dashboard
- Kubernetes Inventory
- Kubernetes Operations
- Kubernetes Governance
- Kubernetes Tenant
- Kubernetes Analytics
- Object Storage Operations Dashboard
- Object Storage Inventory
- Object Storage Analytics

Registry / Harbor operational consumers must adopt this contract when provider-backed Registry pages are introduced. The Harbor integration configuration workspace itself is the setup destination and therefore is not blocked by its own prerequisite.

## Review checklist

- level-3 route navigation remains visible when peer routes exist;
- Hero identity is unchanged by provider absence;
- metadata roles are state-stable;
- Hero-right setup context has no duplicate remediation CTA;
- one below-Hero setup blocker owns remediation;
- normal operational content is not rendered while the provider is absent;
- registered-but-offline is not misclassified as provider absent;
- secondary dependencies do not create a third provider-setup grammar;
- light/dark, responsive, keyboard focus, permissions, and accessibility remain shared-component owned.
