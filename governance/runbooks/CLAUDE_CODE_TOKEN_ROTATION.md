# CLAUDE CODE TOKEN ROTATION | RUNBOOK

Дата версии: 2026-05-22 | 06:02 (UTC+3)
Статус: active

## Назначение
Инструкция описывает, как оператор обновляет Claude Code token для GitHub Actions без передачи секрета агентам, в чат, issue, Telegram или файлы репозитория.

## Когда применять
- Claude/Claude Code сообщает, что прежний token устарел, отозван или больше не работает.
- GitHub Actions Claude workflow падает на authentication / unauthorized / expired token.
- Плановая ротация секрета.

## Как получить новый OAuth token Claude Code
1. На локальной машине оператора открыть терминал.
2. Обновить Claude Code CLI до актуальной версии.
3. Выполнить локально:
   ```bash
   claude setup-token
   ```
4. Пройти OAuth-авторизацию в браузере.
5. Скопировать выведенный token из терминала.

Важно: команда печатает token в терминал и не сохраняет его автоматически. Token нельзя вставлять в репозиторий, чат, issue, Telegram или markdown-файлы.

## Куда вставить token в GitHub
1. Открыть репозиторий GitHub.
2. Перейти: Settings → Secrets and variables → Actions.
3. Выбрать Repository secrets.
4. Если secret уже есть — открыть `CLAUDE_CODE_OAUTH_TOKEN` и нажать Update.
5. Если secret отсутствует — нажать New repository secret.
6. Name: `CLAUDE_CODE_OAUTH_TOKEN`.
7. Value: вставить новый token.
8. Сохранить.

## Важное правило выбора режима auth
Claude GitHub Action должен использовать один понятный режим auth:

### Вариант A — OAuth token подписки Claude
- Secret: `CLAUDE_CODE_OAUTH_TOKEN`.
- Workflow передаёт `CLAUDE_CODE_OAUTH_TOKEN` через env.
- Не хранить token в файлах.

### Вариант B — Anthropic API key
- Secret: `ANTHROPIC_API_KEY`.
- Workflow передаёт API key как secret.
- Не хранить key в файлах.

Если одновременно настроены OAuth token и устаревший/битый API key, возможны authentication failures. При подозрении на конфликт нужно либо обновить `ANTHROPIC_API_KEY`, либо убрать его использование из Claude workflow и оставить OAuth-only режим.

## Проверка после обновления
После обновления секрета агент обязан выполнить smoke-loop:
1. Создать валидный queue item на запуск Claude dispatcher.
2. Получить `governance/workflow_dispatch_results/*.status.json`.
3. Получить `governance/state/claude_inbound_mailbox_workflow_state.json` со start/completion.
4. Получить реальный ответ в `governance/audit_mailbox/claude_to_gpt/`.
5. Не считать fallback/blocker-файлы реальным Claude response.

PASS разрешён только если выполнены все три proof:
- dispatch result exists;
- Claude runtime state exists;
- real Claude response exists.

## Запреты
- Не коммитить token.
- Не писать token в issue comments.
- Не отправлять token в Telegram.
- Не передавать token агенту в чат.
- Не логировать token в workflow output.
- Не объявлять PASS без трёх proof.

## Ответственный контур
Оператор обновляет GitHub secret вручную, потому что агент не должен видеть секрет. Агент после этого запускает smoke-loop и фиксирует только факт проверки, без значения секрета.
