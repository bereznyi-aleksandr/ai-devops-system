# BEM-946 | Push rejected diagnosis
Status: PUSH_REJECTED_CONFIRMED
Date: 2026-05-31

Evidence from operator screenshot:
- Codex Runner job failed at push step.
- Error: rejected main -> main fetch first.
- Meaning: runner made local commit, but remote branch advanced before push.

Correction required:
- codex-runner push step must fetch latest main, rebase local commit and retry push.
- Prior BEM-932..945 file PASS claims must be treated as workflow/local artifacts until non-null commit SHA or remote verification exists.

No issue comments.
