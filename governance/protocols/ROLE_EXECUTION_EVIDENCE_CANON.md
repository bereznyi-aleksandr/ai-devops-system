# BEM-626 | Role Execution Evidence Canon

Дата: 2026-05-18 | 07:25 (UTC+3)

## Зачем

Отчёты должны отличать file-based artifact от реального выполнения роли провайдером.

## Типы выполнения

### 1. artifact_only
Роль представлена файлом/JSON в inbox/outbox. Это доказывает маршрутизацию, но не доказывает live LLM execution.

### 2. gpt_reserve_execution
Роль выполнена GPT reserve через текущий write-канал. Должны быть: task id, commit, proof file, report.

### 3. claude_primary_execution
Роль выполнена Claude Code primary. Должны быть: Claude-authored artifact, provider gate result, proof file, commit/run evidence.

### 4. codex_direct_execution
Роль выполнена Codex/direct repo write внутри внутреннего контура. Должны быть: adapter name, commit, proof file. Deno не считается внутренним executor, если он использовался только как транспорт внешнего GPT.

## Обязательные поля отчёта
- role
- expected_actor
- actual_actor
- execution_type
- adapter
- provider_checked
- selected_provider
- reserve_used
- proof_file
- commit_sha
- blocker

## Запрет
Нельзя писать PASS по Claude primary только потому, что создан файл для Claude или есть mailbox-сообщение.
