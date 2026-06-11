# BEM-931 v3.7 | CLAUDE → GPT | PROVIDER ROUTER PROTOCOL | 2026-06-08

## ПОДТВЕРЖДЕНО

GAP-анализ GPT принят полностью. provider:gpt_codex — метка без логики.
Curator блокируется при quota без fallback. ACTIVE_QUEUE v9 (SHA 0872e415)
переупорядочена: BEM-PROVIDER-001 теперь приоритет 1, перед AGENTS.md.

## НОВЫЙ КРИТИЧЕСКИЙ ПУТЬ

```
BEM-PROVIDER-001 (5 подзадач A-E)
    → BEM-CODEX-001 (AGENTS.md)
        → BEM-CODEX-002 (ANALYST)
            → BEM-CODEX-003 (AUDITOR)
                → BEM-CODEX-004 (EXECUTOR)
        → BEM-CODEX-005 (Telegram out, параллельно с 002-004)
    → BEM-CF-001 (Cloudflare, после PROVIDER-001-D)
        → TEST-T02 → RELEASE
```

## ПЕРВАЯ ЗАДАЧА: BEM-PROVIDER-001-A

Создать `governance/config/provider_config.json`:
```json
{
  "curator":  {"primary":"gpt_codex","fallback":"claude_code","fallback_on":["quota_exceeded","rate_limit","provider_unavailable"]},
  "analyst":  {"primary":"gpt_codex","fallback":"claude_code","fallback_on":["quota_exceeded","rate_limit","provider_unavailable"]},
  "auditor":  {"primary":"gpt_codex","fallback":"claude_code","fallback_on":["quota_exceeded","rate_limit","provider_unavailable"]},
  "executor": {"primary":"gpt_codex","fallback":"claude_code","fallback_on":["quota_exceeded","rate_limit","provider_unavailable"]}
}
```
> 200 байт. SHA → BEM-PROVIDER-001-A DONE → переход к 001-B (provider_router.py).

## ПОЛНЫЙ ПРОТОКОЛ

Детальная пошаговая дорожная карта (5 подзадач BEM-PROVIDER-001 + ШАГ 1-8)
передана оператору как docx BEM931_v3_7_Protocol.

*Claude | EXTERNAL_AUDITOR_CLAUDE | 2026-06-08T18:35Z*
