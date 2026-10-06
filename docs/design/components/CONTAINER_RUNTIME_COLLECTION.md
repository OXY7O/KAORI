# Container Runtime Collection

Use `components/container_runtime_collection.html` for current runtime evidence across regular, init, and ephemeral containers.

## Contract

- canonical table geometry;
- Container, Kind, Runtime State, Image, Restart Activity, and Timing columns;
- regular/init/ephemeral kind is metadata;
- runtime state is derived from state, readiness, and exit code;
- terminated exit code `0` is Completed, not Not Ready;
- terminated non-zero exit code is Failed;
- restart count is cumulative factual evidence, not an automatic severity;
- pull policy remains factual until an explicit governance policy evaluates it;
- missing runtime evidence is Unknown, not Failed.

The component is presentation-only. State derivation belongs in the inventory service.
