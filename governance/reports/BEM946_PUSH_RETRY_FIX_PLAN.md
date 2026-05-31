# BEM-946 | Push retry fix plan
Status: FIX_PLAN_READY
Date: 2026-05-31

Required workflow behaviour:
1. Commit generated files.
2. Before push, run git fetch origin main.
3. Rebase local commit on origin/main.
4. Push.
5. If push rejected again, repeat fetch/rebase/push up to 3 attempts.
6. If still rejected, write explicit blocker with local commit SHA and do not claim remote PASS.

No issue comments.
