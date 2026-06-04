# P15B | Fix codex-task commit_sha response
Status: completed
Date: 2026-06-04

Patched governance/deno_webhook.js so /codex-task can return commit_sha/task_file_commit_sha from the GitHub contents API response. Workflow lock respected: no .github/workflows files touched.

Next: P15C codex-task commit_sha response evidence.
