# BEM-912 External proof policy and CI

Status: PASS_WITH_SHA_GAP

Policy: governance/state/external_proof_policy.json

CI workflow: .github/workflows/governance-validation-ci.yml

Git proof collector: governance/tools/collect_git_proof.sh

Missing: none

Honest gap: current Deno codex-status still reports commit_sha=null; release PASS requires git SHA or Actions run log.
