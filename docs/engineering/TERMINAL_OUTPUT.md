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

## Mandatory capability and gate evidence

Every new or materially changed KAORI feature, domain, capability, provider, operator surface, or validation gate **must** use the existing release-ownership and CI evidence format. This is an admission/review requirement, not a reason to create a new tool or duplicate verifier.

In GitHub Actions, the operator-facing record for each **executed** check must make these fields discoverable using the existing Step Summary, expanded steps and retained artifacts:

- **Identity** — domain/capability/provider or gate owner, and the exact verifier/check label.
- **Purpose / scope** — what contract is protected, its relevant boundaries, and what the check does **not** prove.
- **Execution** — the canonical command or actual test selector; skipped or reused work must not be presented as freshly executed.
- **Result** — PASS/FAIL/SKIP/REUSED (or the existing explicit FALLBACK/NOT RUN/BLOCKED state where applicable), with actual result and elapsed duration.
- **Evidence** — executed verifier/JUnit/security/runtime/DAST output, raw diagnostic artifact or validated run reference, and exact source identity when release-authoritative.
- **Failure** — the first actionable boundary, concise diagnostic context, and a pointer to retained full logs; do not conceal failing checks behind a green aggregate.
- **Traceability** — governing Issue, reviewable PR, owning release surface, test/contract paths, exact SHA and staging/UAT acceptance when applicable.

Registration in the release-surface registry means **REGISTERED**, never an executed test PASS. A static verifier protects only its declared contract; provider functional/security behavior, deployment and human acceptance require their independently executed evidence. Do not add a per-capability PASS status unless a real executed test or verifier justifies it.

Keep ordinary CLI success short and failures actionable. In CI, place a clear purpose next to the actual command and preserve the existing report columns (group, check, purpose/scope, command, outcome, duration and raw-log reference). A new verifier must have a meaningful, specific purpose; the generic fallback description is for legacy coverage only, not an acceptable new-feature specification. Never print secrets to make evidence more verbose.

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
