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
| owner_approval_required | true |
| current_phase | repository cleanup and base structure |
| current_stage | local Codex fallback active |
| last_known_blocker | Claude Code usage limit was observed |
| next_action | GPT curator and local Codex flow prepare next minimal safe step |
| owner_action_required | false |
| curator_schedule | hourly |
| curator_interval_minutes | 60 |
| last_hourly_curator_check | 2026-05-01T18:00:00Z |

## Routing table

| Trigger | Contour | Workflow |
|---|---|---|
| @analyst | claude | analyst.yml |
| @auditor | claude | auditor.yml |
| @executor | claude | executor.yml |
| @claude | claude | claude.yml |
| @codex ROLE=GPT_ANALYST | gpt_codex | manual / gpt |
| @codex ROLE=GPT_AUDITOR | gpt_codex | manual / gpt |
| @codex ROLE=GPT_EXECUTOR | gpt_codex | manual / gpt |

## Последние события

| Время | Источник | Событие |
|---|---|---|
| 2026-05-01T18:00:00Z | gpt-curator | STATE_LAYER_INITIALIZED |
| 2026-05-01T17:42:00Z | auditor-chat | executor.yml исправлен — trigger_phrase + prompt |
| 2026-05-01T17:42:00Z | auditor-chat | auditor.yml исправлен |
| 2026-05-01T17:42:00Z | auditor-chat | analyst.yml исправлен |

## Следующий ожидаемый переход

@analyst → АНАЛИТИК предлагает шаг → @auditor REVIEW → @executor EXECUTE

## Safety rules

1. Fallback включается только по owner approval
2. GPT_EXECUTOR создаёт только draft PR — merge только владелец
3. Переключение контура фиксируется в exchange.jsonl
4. Куратор работает 1 раз в час
5. Куратор не может выполнять действия без owner approval
