# BEM-642 | Workflow Dispatch Token Permissions

Дата: 2026-05-18 | 07:54 (UTC+3)

Workflow dispatch helpers must use `github.token` fallback, not `secrets.GITHUB_TOKEN`. Workflows that dispatch workflows require `actions: write` permission.
