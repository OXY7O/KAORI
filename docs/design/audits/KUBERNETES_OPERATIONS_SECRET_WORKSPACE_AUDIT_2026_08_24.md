# Kubernetes Operations Secret Workspace Audit — 24 Aug 2026

## Scope

Reviewed Secret Management mutation and Protected Reveal surfaces, with emphasis on Create Secret `Target & Identity`, Protected Reveal navigation, semantic palette ownership, typography, responsive geometry, protected-runtime boundaries, accessibility, and operational wording.

## Decisions

- `Target & Identity` uses a two-column grid from the medium breakpoint onward. Four fields therefore render as two rows instead of one dense four-column strip.
- Protected Reveal adopts the Analytics-derived **Tab Style 4 — Content Tabs** visual treatment through the shared `components/content_tabs.html` owner.
- Protected Reveal keeps its existing Alpine state, URL synchronization, keyboard movement, panel visibility, and real server-navigation fallback. The visual migration does not weaken reveal policy, approval, step-up, or one-time payload controls.
- Empty eligible-cluster guidance is shortened to `No eligible cluster. Review readiness or policy.`

## Standardization Review

- **Palette:** Secret templates use KAORI semantic surface/content/outline/status tokens; no page-local raw color family is introduced.
- **Typography:** headings, body copy, supporting copy, and controls stay on the established KAORI scale; no arbitrary font sizes or tracking utilities are introduced.
- **Structure:** ordinary CRUD keeps `form-context-v1`; the New Request reveal task keeps the same shared Form + Right Context contract; registries remain full-width.
- **Tabs:** Content Tabs own geometry and active/inactive visual tokens; the Protected Reveal page owns only controlled view state and URL/deep-link behavior.
- **Security:** live target discovery, namespace policy, approval, step-up, blocked-key, no-store response headers, and one-time reveal behavior are unchanged.
- **Accessibility:** tabs retain labelled tablist/tab/tabpanel relationships, roving keyboard navigation, focus treatment, and progressive href fallback.
- **Wording:** copy stays operational, concise, and evidence-safe; no wording implies that an unavailable target is healthy or policy-compliant.

## Future Rule

Kubernetes Operations pages must reuse the shared operation components and approved tab registry. A new Secret/ConfigMap task must not introduce a local palette, arbitrary typography, duplicated form/context grid, or page-local tab class list.
