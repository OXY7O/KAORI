# KAORI UAT scenario execution and evidence — isolated preparation (#1728)

This is a **manual first-wave evidence evaluator**, not a CI workflow, second Gherkin runner or Human Acceptance engine. It is stacked on #1738 to read the same approved Scenario IDs; #1726/#1727 browser/backend assertions must be integrated on the **exact selected candidate** before actual admission testing. No evidence can be inherited from a previous candidate.

## Before execution

Confirm #1725 QA standard, #1738 scenario catalog, applicable #1726/#1727 test nodes, and the accepted staging **commit SHA/tree SHA**. Server/UAT additionally requires the deployed immutable **OCI sha256 digest**, a sanctioned test account, approved UAT host and disposable provider namespace. Do not run destructive/provider mutations without operator authorization and recovery/cleanup plans.

Use the existing pytest runner/JUnit and Playwright artifact directory. For example, after selecting the admitted candidate (replace placeholders):

~~~bash
python -m pytest -q tests/access/authentication/test_login_characterization.py \
  --junitxml=tmp/ci-artifacts/test-output/uat-pilot.xml
# Execute the remaining manifest nodes via existing pytest/Playwright commands
# after the selected source includes them. Collect all relevant JUnit files.
python -m scripts.uat_scenario_evidence \
  --manifest docs/engineering/uat/scenario_execution_manifest.json \
  --execution /path/to/actual-execution.json \
  --junit tmp/ci-artifacts/test-output/uat-pilot.xml \
  --evidence-root tmp/ci-artifacts/test-output \
  --expected-source REPLACE_WITH_ADMITTED_SOURCE_SHA \
  --expected-tree REPLACE_WITH_ADMITTED_TREE_SHA \
  --output tmp/ci-artifacts/test-output/uat-evidence-dossier.json
~~~

For **server_uat**, provide `--expected-digest sha256:<64hex>` and match the execution record's `candidate.oci_digest`. The example request file is **deliberately unexecutable** until values and paths are replaced; do not copy a simulated/local result into real-provider acceptance.

The execution JSON must contain a nonempty `run.run_id`, `run.runner` and timezone-aware ISO-8601 `run.started_at`; use a fresh evidence directory and JUnit files **from that same run**. The evaluator validates the supplied source SHA/tree/digest against independently provided expected values, but **does not independently authenticate GitHub provenance or the executing infrastructure**; operator review must correlate the run ID, actual CI/local environment and candidate artifacts. Reusing stale files under a new candidate is prohibited.

The scenario mapping file is a bounded selected **pilot subset**, not a declaration that all 91 Gherkin scenarios have been automated. A `nodeid` maps to pytest and a set of six viewport variants (when appropriate). All expected variants must appear in JUnit; a mandatory skipped, failed, missing, or absent-artifact case cannot be counted as machine PASS. For UI scenarios, each mapped browser test and viewport requires its own nonempty screenshot and trace, keyed by `nodeid`, `kind` and `variant` under the verified evidence root. Missing evidence from one UI node cannot be hidden by screenshots from another node. Missing or wrong-source evidence stays incomplete.

For real-provider-required Tenant acceptance, attach sanitized structured JSON for `provider_readback`, `committed_state` and `activity_audit`: each must contain `verified: true`, the exact accepted `source_sha` and matching `run_id`. A file that is absent, empty, incorrectly bound or explicitly unverified is **BLOCKED**. This machine format check does not independently verify that the provider read-back matches reality; the authorized operator must review it. Merely setting `provider_mode: real` is **not sufficient**. Reviewer verification of the actual provider identity and pre/post mutation diff remains mandatory.

The script emits a JSON report, returns **non-zero** when incomplete, and always declares `human_acceptance: PENDING`. An all-machine-PASS report means **READY_FOR_HUMAN_REVIEW**, not accepted UAT. Real-provider-required Tenant evidence cannot be proven by mocks. Reviewer acceptance is separately recorded by an authorized human on the exact candidate in the governing Issue/PR, alongside defects, provider read-back and security/evidence disposition.

Do not publish raw credentials, request tokens, Secret material, kubeconfig, or sensitive data in JUnit, browser screenshots or traces. Ensure redaction/retention follows the current KAORI documentation. The output is local to the selected execution and does **not** change Developer Check, Full Admission or GitHub Actions triggers.
