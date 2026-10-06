# KAORI Data Lifecycle Final Lock v1.1 Audit — 2026-08-08

## Review Findings

1. **Tab sequence:** Storage sat between policy intent and archive evidence. The operator flow is now `Retention Policies → Archive History → Archive Storage`.
2. **Loading indicator drift:** Data Lifecycle used the legacy indeterminate notification segment rather than the shared KAORI loading-bar component. Both policy and history HTMX indicators now use `components/loading_bar.html` inside their headers.
3. **Retention automation ambiguity:** Entering a retention duration could be mistaken for immediate execution. The policy workspace now states that retention days define eligibility; automatic jobs require both policy and schedule enablement.
4. **Failure semantics ambiguity:** The canonical job advertised two attempts but retention tasks did not consume that budget. v1.1 now performs one bounded automatic retry for transient connectivity failures; exhausted/non-retryable failures remain terminal and cleanup stays blocked. Worker-loss redelivery remains a separate Celery reliability mechanism.
5. **Worker topology:** Production already has a dedicated maintenance worker. No additional retention-specific worker is required while `RETENTION_CELERY_QUEUE=maintenance`; custom queues require their own consumer.
6. **Archive Storage density:** The old four-metric card plus one safety strip did not explain target identity, verification strength, worker dependency, or failure handling. The workspace now exposes operational posture, target contract, execution contract, safety boundary, and interpretation.
7. **Pagination typography:** `Rows` inherited a larger parent font. It now uses canonical `text-xs` typography through the shared pagination footer geometry.
8. **Copy density:** Managed-domain and Job Execution descriptions were shortened without losing their operational meaning.
9. **Dark sidebar accent:** The separate 3 px inset Violet line was visually noisy in dark mode. It is removed while preserving the active Violet surface and border.

## Lock Decision

Approved as Data Lifecycle Final Lock v1.1. Future changes must preserve the execution ownership boundary, fail-closed archive-first cleanup, canonical loading/pagination components, and the operational information architecture above.
