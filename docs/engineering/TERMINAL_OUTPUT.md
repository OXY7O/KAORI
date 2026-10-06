# KAORI Terminal Output Standard

KAORI-operated commands must be easy to scan in local terminals and GitHub Actions while preserving raw diagnostics when a failure needs investigation.

## Canonical shape

```text
== KAORI <Area> · <Stage> ==
  identity : concise value
  target   : concise value
PASS — <result>
  evidence : concise evidence
  next     : operator action when one is required
```

Use `PASS`, `FAIL`, `SKIP`, and `REUSED` as stable result vocabulary. Normal success output should stay short. A failure must identify the first actionable boundary, then allow the underlying tool to print its raw diagnostic output.

## Terminology

Use these operator-facing terms consistently:

- Development
- Staging
- Production
- Developer Check
- Full Admission
- Staging Validation
- Staging Acceptance
- Production Promotion
- Host

Legacy `UAT` or `VPS` wording should not be introduced on new operator surfaces.

## Security

Never print secret values, tokens, passwords, private keys, credential-bearing URLs, or unredacted environment dumps. Identifiers such as source SHA, version, immutable image digest, environment name, and non-secret provider endpoint labels may be printed when operationally useful.

## Compatibility

Unicode symbols may be used sparingly in interactive/operator summaries, but semantic meaning must never depend on color or icons. CI and redirected output must remain understandable as plain text.
