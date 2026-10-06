# Dark Mode Standard Alignment Audit — August 2026

**Status:** Current implementation audit
**Decision:** Adopt neutral-first dark mode with controlled KAORI Violet.

## Initial findings

The previous dark palette was technically tokenized but visually too uniform:

- the page canvas and main shell had insufficient surface separation;
- the Hero used the same Bright Violet role as primary actions;
- active sidebar parents looked like large CTA buttons;
- muted text retained too much Lavender character;
- cards relied on outlines because page, shell, and content surfaces were too close;
- the design system prohibited all authenticated gradients while the preferred Hero direction required a controlled exception;
- no dedicated dark-mode verifier locked implementation and documentation together.

## Remediation

- Added `surface-shell`, `surface-muted`, and `surface-sunken` layers.
- Rebalanced dark content and outline tokens toward neutral Violet-gray values.
- Added Hero-owned background, panel, tile, chip, and outline tokens.
- Replaced the dark active-sidebar solid fill with a translucent active surface and left accent.
- Added shared classes for shell, Hero, sidebar, workspace cards, and brand-domain panels.
- Updated the Welcome workspace catalog to consume the new shared classes.
- Added `components/DARK_MODE.md` as the authoritative dark-mode standard.
- Added `scripts/verify_dark_mode_standard.py` and contract tests.
- Registered the verifier in the static quality gate.

## Non-goals

This change does not individually redesign every domain page. Existing templates that already use semantic surface/content/outline tokens inherit the new palette automatically. Raw color debt outside the shared shell remains governed by the existing UI style-debt process.

## Resulting authority

```text
DARK_MODE.md
    ↓
frontend/styles.css
    ↓
shared shell / sidebar / Hero components
    ↓
app/static/css/output.css
    ↓
verifier and contract tests
```

## Validation evidence

The aligned implementation passed the focused quality gates:

- dark-mode standard verifier;
- Hero and sidebar standard verifiers;
- UI style-debt verifier;
- compiled CSS contract verifier;
- 41 focused design and Welcome contract tests;
- Python syntax validation across 801 source files;
- Jinja parsing across 531 templates;
- CSS parsing for both source and compiled stylesheets;
- `git diff --check`.

Measured dark-mode contrast ratios include:

| Pair | Ratio |
|---|---:|
| Primary text on page canvas | 17.49:1 |
| Secondary text on page canvas | 11.44:1 |
| Muted text on page canvas | 6.70:1 |
| Primary text on card | 15.64:1 |
| Muted text on card | 5.99:1 |
| Sidebar muted text on sidebar | 8.81:1 |

The repository-wide contract suite remains at 485 passed and 18 failed. Those failures are existing baseline drift outside this dark-mode change, concentrated in Analytics, Jobs, Kubernetes, and Reports. The focused dark-mode work introduced no additional contract failure.

## Environment constraints during the audit

The canonical Tailwind source was updated in `frontend/styles.css`. The compiled stylesheet was aligned with an equivalent deterministic override block because the isolated audit environment could not complete `npm ci`; the configured package registry did not provide `to-regex-range@5.0.1`. The compiled CSS verifier and CSS parser both passed after the alignment.

`ruff` was not available in the audit environment. Python syntax validation, focused contract tests, Jinja parsing, CSS verification, and the design-specific quality gates were used instead. Normal KAORI CI or the Dev Container should still execute the full lint and frontend build pipelines before release.
