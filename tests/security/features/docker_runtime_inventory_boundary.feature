# Security proof specification only — not wired to an automated Gherkin runner.
# No scenario below has been executed. Run only on an approved disposable host.
# Authority: OXY7O/KAORI #2013; runbook: docs/security/docker-runtime-inventory-disposable-poc.md
@disposable @manual @security @not_executed
Feature: Privilege-contained read-only Docker and Compose inventory
  As a KAORI security reviewer
  I want a host-enforced restricted inventory boundary
  So that compromise of the inventory SSH credential cannot mutate a Docker host

  Background:
    Given a dedicated disposable Linux VM has been approved by its owner
    And its OpenSSH and Docker Engine versions are recorded
    And its SSH host key was independently verified and pinned
    And a dedicated inventory SSH identity has no docker group or general sudo membership
    And a host-owned fixed-command collector was independently approved and installed
    And synthetic canary containers were recorded before the test

  @SEC-01 @positive
  Scenario: Exact snapshot operation returns only a bounded schema
    When the inventory identity requests the approved snapshot command
    Then the host runs only the reviewed collector
    And the response is one valid versioned JSON snapshot
    And the response contains only allowlisted fields
    And the canary Docker resources remain unchanged

  @SEC-02 @negative
  Scenario Outline: Unapproved command cannot run as a shell
    When the inventory identity sends the unapproved command "<command>"
    Then the host rejects the request before privileged execution
    And the command is not executed
    And the canary Docker resources remain unchanged
    Examples:
      | command                    |
      | echo UNAUTHORIZED_COMMAND  |
      | sh -c true                 |
      | python3 -c pass            |
      | docker ps                  |
      | docker stop canary         |

  @SEC-03 @negative
  Scenario Outline: SSH ancillary access is disabled
    When the inventory identity attempts "<access>"
    Then the SSH server rejects that access
    And no raw Docker daemon or alternative host shell becomes reachable
    Examples:
      | access                       |
      | interactive shell             |
      | PTY allocation                |
      | SFTP subsystem                |
      | SCP transfer                  |
      | local TCP forwarding          |
      | remote TCP forwarding         |
      | StreamLocal socket forwarding |
      | agent forwarding              |
      | X11 forwarding                |

  @SEC-04 @negative
  Scenario: Inventory identity has no reusable daemon privilege
    When the lab administrator inspects effective account groups and privileges
    Then the inventory identity is neither root nor a member of docker
    And it has no arbitrary privileged command or interpreter
    And all collector executable and config paths are administrator-owned and non-writable

  @SEC-05 @negative
  Scenario Outline: Daemon mutations cannot be reached through inventory identity
    When the inventory identity attempts "<operation>" against disposable canary assets
    Then the host boundary denies the operation
    And the Docker daemon does not receive an authorized mutation for it
    And the canary resources remain unchanged
    Examples:
      | operation            |
      | create container     |
      | start container      |
      | stop container       |
      | exec in container    |
      | delete container     |
      | create volume        |
      | mount host directory |
      | connect Docker socket|

  @SEC-06 @negative
  Scenario Outline: Collector invocation rejects untrusted parameters
    When the inventory identity supplies "<tampering>"
    Then no unapproved executable, method, argument, environment or path is used
    And the request is denied with a sanitized error
    Examples:
      | tampering                          |
      | altered SSH_ORIGINAL_COMMAND       |
      | user-selected Docker API URL       |
      | user-selected container identifier |
      | user-selected output format        |
      | injected environment variable      |
      | symlink replacement                |
      | user-writable helper replacement   |

  @SEC-07 @negative
  Scenario: Unverified SSH host-key rotation fails closed
    Given the destination presents a host key that differs from the approved identity
    When the inventory worker attempts the snapshot
    Then the worker refuses SSH authentication
    And it does not automatically trust the replacement key
    And no collection is attempted on the new endpoint

  @SEC-07 @negative
  Scenario: Revoked inventory credential cannot run a snapshot
    Given the host owner has revoked the approved inventory credential
    When the old inventory identity attempts the snapshot
    Then SSH authentication is rejected
    And no collector result is accepted as current evidence

  @SEC-08 @negative
  Scenario: Synthetic secret-bearing Docker metadata never escapes host projection
    Given a canary has synthetic secret markers in environment variables
    And the canary has arbitrary labels and sensitive-looking mount path markers
    When the restricted snapshot is collected
    Then only validated Compose project and service labels may be emitted
    And no synthetic secret or mount marker appears in stdout or stderr
    And no unapproved raw inspect or provider response is stored as KAORI evidence

  @SEC-09 @recovery
  Scenario Outline: Failed provider read does not widen access
    Given the Docker source fails with "<fault>"
    When the collector requests the bounded observation
    Then the collector emits a sanitized incomplete or failed result
    And it does not retry through a privileged alternate transport
    And KAORI preserves the last qualified committed snapshot
    Examples:
      | fault                     |
      | socket permission denied  |
      | daemon unavailable        |
      | request timeout           |
      | unsupported API version   |

  @SEC-10 @recovery
  Scenario Outline: Malformed or oversized data fails without false completeness
    Given Docker returns "<response>"
    When the collector normalizes the snapshot
    Then the result is bounded and safely rejected or explicitly incomplete
    And no truncation is marked as complete
    And no raw provider exception containing synthetic secrets is emitted
    Examples:
      | response                  |
      | invalid JSON              |
      | oversized container list  |
      | extreme field length      |
      | wrong field type          |
      | control characters        |

  @SEC-11 @concurrency
  Scenario: Superseded source attempt cannot replace newer committed evidence
    Given source revision 4 was requested by collector A
    And source revision 5 was committed by collector B
    When collector A returns a delayed successful snapshot
    Then KAORI rejects collector A's commit
    And revision 5 remains the current committed source
    And the rejected attempt remains auditable

  @SEC-12 @identity
  Scenario: Local image ID never becomes a verified registry digest
    Given the collector has an image ID but no qualified repository digest
    When the observation is committed
    Then the image is recorded with local identity only
    And no strong OCI Registry Artifact match is created

  @SEC-13 @safety
  Scenario: Repeated inventory run leaves disposable containers intact
    Given no synthetic canary state changed outside the collector
    When the exact snapshot command runs repeatedly
    Then the canary containers, mounts and volumes remain unchanged
    And the resulting records contain source-qualified timestamps
    And no general Docker daemon privilege was granted to the SSH identity

  @SEC-14 @lifecycle
  Scenario: Revoked collector can no longer be called
    Given the host owner has retired the lab collector
    When the former inventory identity attempts the snapshot
    Then the host rejects the request
    And the Docker daemon remains inaccessible through that identity
    And the inventory source is no longer presented as current

  @scope @negative
  Scenario: A collector cannot assign its own KAORI tenant or authorization
    Given a syntactically valid snapshot contains untrusted owner metadata
    When KAORI validates the snapshot envelope
    Then tenant and scope come only from canonical source admission
    And any self-asserted privilege or authorization field is ignored or rejected
    And the accepted evidence is bounded to the registered source generation
