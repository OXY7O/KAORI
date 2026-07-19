# KAORI Typography Baseline — July 2026

## Purpose

This document records the typography patterns already established across KAORI and converts them into a stable baseline for future implementation and audit work.

It is not a claim that every existing template is already compliant. It defines the target state against which subsequent template audits and migrations must be performed.

## Current implemented direction

KAORI already consistently trends toward the following hierarchy:

- Hero titles at approximately 24–30 px.
- Major page/section titles at approximately 20–24 px.
- Card, modal, drawer, and table-block titles at approximately 16–18 px.
- Primary content and resource names at 14 px.
- Descriptions and supporting text at 12–14 px.
- Table and filter labels at 12 px.
- Compact status labels at 10 px.
- Compact table actions at 12 px.

The preferred title weight is semibold. Bold is reserved for higher-emphasis hero or KPI use cases.

## Existing design conventions consolidated

### Titles

Visible content titles generally use Title Case and primary content color. Uppercase remains intentional for compact eyebrow labels and abbreviations rather than ordinary titles.

### Descriptions

Descriptions and guidance use sentence case, regular weight, and muted/secondary color.

### Tables

The table baseline is:

- 12 px semibold headers;
- 14 px primary and ordinary values;
- 12 px supporting context;
- 10 px compact semantic labels;
- 12 px compact actions.

### Buttons

Button labels use Title Case. Table actions are compact and generally limited to concise wording. Font geometry remains consistent across ordinary and destructive actions.

### Semantic labels

Labels are intentionally smaller than ordinary content and are used only where status/category semantics justify them.

### Technical values

Kubernetes resource names, provider versions, hashes, IDs, paths, metrics, commands, and similar values preserve their original casing. Monospace is contextual rather than global.

## Problems this standard is intended to prevent

- inconsistent `bold` versus `semibold` usage for equivalent titles;
- mixed Title Case, sentence case, uppercase, and CSS `capitalize` across equivalent components;
- arbitrary local font sizes;
- overuse of Violet title text;
- oversized labels or undersized body content;
- decorative icon and label usage that increases visual noise;
- local font-family declarations;
- technical identifiers being incorrectly transformed into Title Case.

## Required follow-up audit

A full template audit should classify visible text into semantic roles and check:

- local `text-[Npx]` declarations;
- ordinary headings using `uppercase` or `capitalize`;
- expanded tracking outside approved eyebrow/metadata cases;
- `font-bold` where semibold is sufficient;
- title text using Violet without interactive or semantic reason;
- equivalent components using different sizes or weights;
- form and filter labels that are not Title Case;
- buttons with inconsistent casing;
- technical values altered by casing filters.

## Target compliance state

The target is not to make every text node identical. The target is a controlled hierarchy with a small approved type scale and predictable casing rules.

A page is compliant when equivalent semantic roles look equivalent, narrative content remains readable, technical casing is preserved, and emphasis is intentional rather than accidental.
