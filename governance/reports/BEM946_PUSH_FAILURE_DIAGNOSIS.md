# BEM-946 | Git push failure diagnosis
Status: PUSH_FAILURE_CONFIRMED
Date: 2026-05-31

Observed from GitHub Actions screenshot:
- Workflow: Codex Runner v3
- Job summary showed local status completed and local SHA.
- Actual job failed on push step with: failed to push some refs / fetch first.
- Cause: remote main changed while runner was committing local result. Local commit SHA is not sufficient proof if push failed.

Decision:
- Treat affected run as not release proof.
- Stabilize codex-runner push path with pull --rebase and retry push.
- Add push conflict evidence policy.

No issue comments.
