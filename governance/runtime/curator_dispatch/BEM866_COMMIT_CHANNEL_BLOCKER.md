# BEM-866 commit channel blocker
Status: BLOCKED_COMMIT_SHA_NULL_SYSTEMIC
Observed:
- codex-runner task results show changed_files but commit_sha=null.
- GitHub workflow_dispatch sees default branch state, not current workspace patches.
- Claude workflow dispatch can be queued/dispatched only against default branch workflows.
Impact:
- Cannot prove Claude mailbox write until repository commit/push contour is restored.
Next required repair:
- Restore codex-runner commit/push/reporting so changed_files produce commit_sha and workflow changes reach default branch.
No issue comments.
