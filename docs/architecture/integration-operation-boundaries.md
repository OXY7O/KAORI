# Integration Operation and Route Boundaries

## Worker Contract

Integration workers dispatch provider operations through
`execute_integration_operation()`. Workers may load shared job and binding
records, but they must not import provider service functions directly.

Prometheus and Alertmanager publish `binding.validate` through their registered
adapter modules. The operation is assigned to the `integration-validation`
queue and uses the same registry authority as runtime validation and health
refresh.

## Route Contract

`app/integrations/routes.py` owns HTTP concerns only:

- request parsing;
- permission checks;
- redirect or HTMX response selection;
- operational feedback presentation.

Provider record lookup and cross-provider binding creation are delegated to:

- `app/integrations/repository.py`;
- `app/integrations/binding_service.py`.

Routes must not query Kubernetes, Prometheus, Alertmanager, or Cluster models
directly and must not import provider binding services.
