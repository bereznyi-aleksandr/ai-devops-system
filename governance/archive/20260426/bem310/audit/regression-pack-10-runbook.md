# Regression Pack 10 Runbook

## Purpose
Repeat the full R-01...R-10 regression verification after governance changes.

## Local run
cd "$HOME/ai-devops-system"
git fetch origin main
git pull --ff-only origin main
python3 governance/scripts/regression_pack_10.py

Expected local result:
REGRESSION_PACK_10_TOTAL=10
REGRESSION_PACK_10_PASSED=10
REGRESSION_PACK_10_FAILED=0
REGRESSION_PACK_10_RESULT=PASS

## GitHub Actions run
gh workflow run regression-pack-10.yml --ref main
gh run list --workflow regression-pack-10.yml --branch main --limit 1

Expected GitHub Actions result:
run_status=completed
run_conclusion=success
pack_total=10
pack_passed=10
pack_failed=0
pack_all_pass=true

## Acceptance rule
The regression pack is accepted only when all 10 tests pass in one run.
