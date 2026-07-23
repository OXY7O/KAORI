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
