# BEM-527 | Healthcheck Matrix

Дата: 2026-05-17 | 11:59 (UTC+3)

| Check | Expected | Action on failure |
|---|---|---|
| Deno version | 4.9+ | Restore webhook /codex-task and /codex-status |
| Workflow triggers | workflow_dispatch only | Remove schedule trigger |
| Executor | ubuntu-latest Python v3 | Revert paid API/Codex CLI path |
| Result status | completed with commit_sha | Diagnose blocker or missing result |
| Roadmap blocker | null | Run one recovery block or direct patch request |
| Issue #31 | no comments | Stop and record critical violation |
