# BEM-842 | Claude OAuth Variant A | Operator Steps

Дата: 2026-05-22 | 11:23 (UTC+3)

1. Install/verify Claude GitHub App access for repository bereznyi-aleksandr/ai-devops-system.
2. On a local machine with Claude Code, run: claude setup-token
3. Copy the generated OAuth token.
4. In GitHub repository Settings -> Secrets and variables -> Actions -> New repository secret, create/update CLAUDE_CODE_OAUTH_TOKEN.
5. Do not add ANTHROPIC_API_KEY for this variant. The workflows now use only claude_code_oauth_token.
6. After secret is saved, run BEM-843 smoke: dispatch result -> Claude runtime state -> real Claude response.
No secrets in repo.
