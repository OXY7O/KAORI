# Welcome Styling Audit — July 2026

## Scope

Reviewed:

- `app/templates/welcome/index.html`;
- `app/static/js/welcome.js`;
- shared label and empty-state components;
- Welcome contract tests;
- KAORI Styling Guide reuse and style-drift guardrails.

## Decisions

1. Retain the canonical `page_hero` implementation without page-local variation.
2. Retain a simplified dark Violet capability anchor as a documented Welcome-only pattern.
3. Introduce a reusable `workspace_link_card` for destination catalogs.
4. Merge access scope and visible result count into catalog metadata; remove the separate Violet summary strip.
5. Replace scope pills with borderless metadata labels.
6. Replace the custom search empty state with the shared empty-state partial.
7. Remove decorative circles, decorative star treatment, heavy hover translation, and excessive shadow.
8. Remove ineffective JavaScript assignment to `group.open` on a non-`details` element.

## Hierarchy correction

The page previously used arbitrary 9–12 px text, `font-extrabold`, custom letter spacing, and a second 24 px section heading beneath the hero. The reviewed page now uses only documented font roles:

- section title: 18 px semibold;
- workspace title: 16 px semibold;
- body/search input: 14 px;
- description and contextual label: 12 px;
- compact scope metadata: shared label component.

## Reusable additions

- `components/welcome_capability_group.html` — Welcome-specific category anchor and group shell;
- `components/workspace_link_card.html` — reusable destination card;
- `patterns/WELCOME_WORKSPACE_CATALOG.md` — landing-page catalog contract.

## Guardrail impact

The Welcome template no longer owns arbitrary font sizes, compact pills, custom label geometry, destination-card geometry, or an inline empty-state implementation. The style baseline is reduced in the same change.
