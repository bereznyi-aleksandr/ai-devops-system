# EXCHANGE — AI DevOps System ISA State
Версия: v1.0 | Дата: 2026-05-01

## Текущее состояние

| Параметр | Значение |
|---|---|
| repository | bereznyi-aleksandr/ai-devops-system |
| main_issue | #31 |
| active_contour | gpt_codex_local |
| fallback_contour | gpt_codex_local |
| fallback_enabled | true |
| fallback_reason | Claude Code usage limit reached; owner approved local Codex CLI fallback |
| owner_approval_required | major_changes_only |
| current_phase | repository cleanup and base structure |
| current_stage | local Codex fallback active |
| last_known_blocker | Claude Code usage limit was observed |
| next_action | GPT local Codex flow continues autonomous minimal safe repository cleanup |
| owner_action_required | false |
| curator_schedule | hourly plus one-shot checks when pending ISA result exists |
| curator_interval_minutes | 60 |
| last_hourly_curator_check | 2026-05-01T18:00:00Z |

## Routing table

| Trigger | Contour | Workflow |
|---|---|---|
| @analyst | claude | analyst.yml |
| @auditor | claude | auditor.yml |
| @executor | claude | executor.yml |
| @claude | claude | claude.yml |
| @gpt_analyst | gpt_codex_local | codex-local.yml |
| @gpt_auditor | gpt_codex_local | codex-local.yml |
| @gpt_executor | gpt_codex_local | codex-local.yml |
| @codex ROLE=GPT_ANALYST | gpt_codex | manual / gpt |
| @codex ROLE=GPT_AUDITOR | gpt_codex | manual / gpt |
| @codex ROLE=GPT_EXECUTOR | gpt_codex | manual / gpt |

## Последние события

| Время | Источник | Событие |
|---|---|---|
| 2026-05-02T07:03:00Z | assistant | AUTONOMY_POLICY_SYNCED |
| 2026-05-02T06:47:00Z | codex-local | ROUTING_TABLE_UPDATED |
| 2026-05-01T18:00:00Z | gpt-curator | STATE_LAYER_INITIALIZED |
| 2026-05-01T17:42:00Z | auditor-chat | executor.yml исправлен — trigger_phrase + prompt |
| 2026-05-01T17:42:00Z | auditor-chat | auditor.yml исправлен |
| 2026-05-01T17:42:00Z | auditor-chat | analyst.yml исправлен |

## Следующий ожидаемый переход

@gpt_analyst → GPT_ANALYST предлагает шаг → @gpt_auditor REVIEW → @gpt_executor EXECUTE

## Safety rules

1. Routine state-layer sync does not require owner approval.
2. Owner approval is required only for architecture changes, permissions, secrets, billing, production deploy, auto-merge, destructive actions, or runner install/reinstall.
3. During fallback, use only @gpt_analyst / @gpt_auditor / @gpt_executor for the active ISA cycle.
4. Do not mix Claude and local Codex role triggers inside one cycle.
5. GPT_EXECUTOR performs only the current approved role scope and does not expand scope.
