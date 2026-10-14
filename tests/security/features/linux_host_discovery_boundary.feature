# Specification only. No Gherkin runner registered; all scenarios NOT_EXECUTED.
# Parent OXY7O/KAORI #1907; host-only issue #2014; independent Docker security #2013.
@manual @disposable @security @not_executed
Feature: Governed Linux host-only discovery with qualified SSH trust
  As a KAORI infrastructure operator
  I want to observe minimal host facts from an authorized Linux target
  So that KAORI can identify and monitor hosts without silently gaining mutation privileges

  Background:
    Given a disposable Linux host belongs to an approved KAORI source scope
    And the SSH host key has been independently verified
    And the dedicated facts account is non-root without sudo or Docker group access
    And the worker uses a reviewed, pinned Ansible execution environment
    And the operation is registered through canonical JobExecution

  @HOST-01 @positive
  Scenario: Approved host observation commits only permitted facts
    When the host observation job executes the approved facts profile
    Then the source identity and SSH peer are verified
    And only approved OS, kernel, architecture and provenance facts are projected
    And the committed observation records source generation and JobExecution attempt
    And the host is not automatically granted managed-asset mutation scope

  @HOST-02 @negative
  Scenario Outline: Unqualified SSH identity blocks collection
    Given the host trust condition is "<condition>"
    When the host facts worker attempts its SSH connection
    Then the connection is rejected before remote fact collection
    And no host key is automatically accepted
    And any previous qualified observation remains available as last-known evidence
    Examples:
      | condition                      |
      | missing verified fingerprint  |
      | changed host key              |
      | untrusted host CA             |
      | expired SSH credential        |
      | revoked SSH credential        |

  @HOST-03 @negative
  Scenario Outline: Cross-scope host discovery is not authorized
    Given the requested target violates "<scope>"
    When an operator or worker attempts discovery
    Then server-side or worker preflight authorization denies the operation
    And no SSH connection is initiated to the unauthorized target
    Examples:
      | scope                       |
      | another tenant              |
      | another environment         |
      | another registered host     |
      | unapproved address alias    |

  @HOST-04 @negative
  Scenario: Minimal facts account does not inherit Docker or mutation permissions
    When the lab administrator inspects the facts account privilege boundary
    Then the account is not root
    And it is not a member of the docker group
    And the fact collection profile does not use become, sudo, shell or raw Docker API
    And no package, firewall, systemd or host configuration mutation is requested

  @HOST-05 @identity
  Scenario: Cloned machine-id and duplicate hostname do not merge two hosts
    Given two independently registered targets have the same machine-id and hostname
    When each target commits qualified host facts
    Then two distinct source-qualified observations remain
    And KAORI does not infer that both targets are the same asset
    And the identity conflict is visible for governed review

  @HOST-06 @identity
  Scenario: Reused IP after a host rebuild cannot transfer ownership
    Given an approved host observation belongs to a previous OS incarnation
    And a different OS incarnation later appears on its former IP
    When KAORI reconciles the newer host observation
    Then the prior observation remains attributed to the prior source identity
    And a new asset relationship is not created without identity verification
    And prior approval does not authorize management of the new host

  @HOST-07 @recovery
  Scenario Outline: Failed collection does not delete last-qualified host evidence
    Given an authorized source has a previously committed observation
    And collection fails with "<fault>"
    When the canonical JobExecution records the attempt
    Then the previous committed observation remains last-known
    And freshness or collection failure is visible with sanitized reason
    And no missing-host or deletion conclusion is inferred
    Examples:
      | fault                   |
      | SSH connection timeout  |
      | denied SSH permission   |
      | malformed facts payload |
      | incomplete facts        |
      | worker cancellation     |

  @HOST-08 @negative
  Scenario: Unreviewed executable local facts never execute
    Given the disposable host contains a canary executable local fact
    When the pinned minimal Ansible setup profile runs
    Then the unapproved local fact is not executed
    And the canary side effect is absent
    And no arbitrary plugin or lookup extends fact collection scope

  @HOST-09 @concurrency
  Scenario: Older source revision cannot overwrite newer facts
    Given collector A started with source revision 3
    And collector B committed a qualified source revision 4
    When collector A completes later
    Then source revision 3 is rejected as stale
    And the revision 4 observation remains authoritative
    And both attempts retain correct auditable job lineage

  @HOST-10 @negative
  Scenario: Synthetic secret markers are redacted before evidence persists
    Given a disposable host produces a synthetic secret marker in an unexpected fact
    When the observation is normalized
    Then that marker does not appear in committed inventory
    And it does not appear in JobExecution, logs, activity audit or exported evidence
    And the worker retains a sanitized diagnostic if collection fails

  @HOST-11 @recovery
  Scenario: Worker-loss retry preserves source generation
    Given a facts worker was interrupted before recording terminal evidence
    When a retry is admitted through the canonical Jobs contract
    Then the attempt is rechecked against current source revision and host identity
    And no stale result can overwrite newer committed observations
    And job expiry is not interpreted as proof that the host was deleted

  @HOST-12 @governance
  Scenario: Host reachability is not an authority to access Docker
    Given the host facts worker successfully verifies SSH and OS evidence
    When KAORI evaluates available asset capabilities
    Then Docker readiness remains unverified until its independent security and provider checks
    And the host remains subject to explicit adoption and operation approval
    And the worker does not gain access to the Docker daemon
