# Secret names for operator review

Values must never be written to repository files.

Required/possible secret names:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_WEBHOOK_SECRET
- AI_SYSTEM_GITHUB_PAT
- GITHUB_TOKEN / GITHUB_PAT as allowed by GitHub Actions context
- CLAUDE_PROVIDER_TOKEN if live provider runtime is enabled by operator
- CODEX_PROVIDER_TOKEN if separate provider secret is required

Status: names only, no values.
No issue comments.
