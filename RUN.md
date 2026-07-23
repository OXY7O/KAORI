# Apply

```bash
unzip -o kaori_domain7_intelligence_evidence_consistency.zip -d .
```

# Validate

```bash
pytest -q \
  tests/intelligence/test_current_generation_recommendations.py \
  tests/contracts/intelligence/test_domain7_current_generation_contract.py

pytest -q tests/intelligence tests/contracts/intelligence
python scripts/verify_architecture_boundaries.py
bash scripts/quality_gate.sh
```

# Commit

```bash
git add \
  app/intelligence/service.py \
  tests/intelligence/test_current_generation_recommendations.py \
  tests/contracts/intelligence/test_domain7_current_generation_contract.py \
  docs/architecture/domain-7-intelligence-evidence-consistency.md \
  PATCH_MANIFEST.md

git commit -m "fix(intelligence): use committed inventory evidence"
```

## Resolver Production-Readiness Evidence

Validate a Domain 20 readiness evidence file before advancing a resolver rollout:

```bash
python scripts/verify_resolver_production_readiness.py \
  path/to/evidence.json \
  --rollout-stage canary
```

Exit codes:

- `0`: all required checks passed.
- `1`: evidence is valid JSON, but one or more readiness checks failed or are missing.
- `2`: the file is missing, unreadable, invalid JSON, contains a non-object root, or includes unknown checks.

The command prints a deterministic evidence hash that can be compared with the stored rollout record. It does not update KAORI database state or advance the rollout stage.
