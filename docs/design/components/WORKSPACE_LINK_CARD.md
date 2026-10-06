# Workspace Link Card

## Purpose

`app/templates/components/workspace_link_card.html` is the canonical destination card for opening a KAORI workspace from a catalog or overview page.

Use it when the entire card navigates to one permission-aware workspace. Do not use it for metrics, operational state, destructive actions, or multi-action records.

## Content contract

Each card contains:

1. one workspace icon;
2. one scope metadata label;
3. one functional label;
4. one workspace title;
5. one concise description;
6. one `Open Workspace` affordance.

The input object provides `href`, `title`, `label`, `description`, `icon`, `scope`, and `search_text`.

## Visual contract

- standard card radius: `rounded-xl`;
- standard card border and `bg-surface-card`;
- restrained `shadow-sm`, increasing only to `shadow-md` on hover;
- no hover translation or large floating shadow;
- 40 px icon surface using Violet Soft;
- title: `text-base font-semibold`;
- description: `text-xs leading-5`;
- scope: `table_label.metadata_label(...)`;
- footer action: `text-sm font-semibold` with a compact arrow surface.

## Interaction contract

- the complete card is one link;
- keyboard focus uses the shared Violet focus ring;
- the accessible label identifies the destination;
- permission filtering occurs before rendering;
- client-side search may only filter cards already rendered for the user.

## Reuse rule

Use this component for Welcome and future catalogs that navigate to peer KAORI workspaces. Do not copy its class bundle into page templates. Extend the component only when the new behavior is reusable across modules.
