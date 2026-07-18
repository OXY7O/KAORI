# KAORI architecture references

Use these documents as stable development context before changing cross-domain behavior.

Read the references in this order:

1. `../product/README.md`: canonical KAORI platform direction, capability boundaries, maturity labels, page-review contract, and wording rules.
2. `module-structure.md`: default package, dependency, service, and README rules.
3. `integration-lifecycle.md`: mandatory lifecycle followed by every external integration.
4. `integration-runtime.md`: shared runtime, health, diagnostics, snapshot, and refresh architecture.
5. `provider-adapter.md`: provider adapter responsibilities and testing contract.
6. `capability-framework.md`: canonical capability discovery and feature-readiness rules.
7. `compatibility-framework.md`: version/profile mapping and limitation rules.
8. `consumer-pattern.md`: asset-consumer boundary and simplified primary/secondary/fallback flow.

Domain-specific rules live beside complex code in `app/<domain>/README.md`. General architecture rules belong here, while product direction belongs in `docs/product`, to avoid duplicated and drifting documentation.
