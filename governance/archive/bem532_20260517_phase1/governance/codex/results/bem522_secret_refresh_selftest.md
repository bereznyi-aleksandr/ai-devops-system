# Codex CLI Result - bem522_secret_refresh_selftest

| Field | Value |
|---|---|
| Trace | bem522_secret_refresh_selftest |
| Executor | Codex CLI |
| Runner | self-hosted codex-local |
| Status | failed |
| Commit SHA | none |
| Changed files | none |
| Completed at | 2026-05-17T04:49:01Z |

## Status: FAILED

### Blocker
```json
{
  "code": "CODEX_EXEC_FAILED",
  "message": "codex exit=1",
  "stderr_tail": "_secret_refresh_selftest.txt with content 'Codex CLI after OPENAI_API_KEY refresh 2026-05-17.' Commit it. No issue comments.\nwarning: Codex could not find bubblewrap on PATH. Install bubblewrap with your OS package manager. See the sandbox prerequisites: https://developers.openai.com/codex/concepts/sandboxing#prerequisites. Codex will use the bundled bubblewrap in the meantime.\nERROR: Quota exceeded. Check your plan and billing details.\nERROR: Quota exceeded. Check your plan and billing details."
}
```

## Notes
- Runner: [self-hosted, codex-local] on Google Cloud VM
- Auth: printenv OPENAI_API_KEY | codex login --with-api-key
- Sandbox: --sandbox workspace-write
- No issue #31 comments (BEM-476/522)
