# Codex fallback provider contract

Provider ID: GPT-CODEX-FALLBACK
Allowed logical roles: auditor, executor

Contract:
- Используется только при provider_failover_policy condition.
- Заменяет Claude Auditor или Claude Executor при limit/unavailable/operator-approved fallback.
- Должен фиксировать fallback_used=true и fallback_reason.
- Не становится canonical primary provider без policy update.
