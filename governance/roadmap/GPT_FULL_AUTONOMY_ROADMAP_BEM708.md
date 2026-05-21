# BEM-708 | GPT FULL AUTONOMY ROADMAP

Дата: 2026-05-20 | 22:54 (UTC+3)
Версия: v1.0-2026-05-20
Статус: ROADMAP_DRAFT_FOR_OPERATOR

## Цель
Создать доказанную автономность GPT: GPT сам получает сигнал/пробуждение, сам проверяет Claude mailbox, сам фиксирует результат в repo, сам продолжает согласование до APPROVED / CHANGE_REQUIRED / BLOCKED, без участия оператора в рутинном цикле.

## Критерий полной автономности

| № | Критерий | PASS только если | Обоснование |
|---|---|---|---|
| 1 | GPT-side wake-up | Есть task-card/confirmation recurring ChatGPT Task и факт запуска после создания | Без доказанного пробуждения GPT нет полной автономности |
| 2 | Repo-side mailbox detection | Claude response в mailbox автоматически превращается в state/handoff/pending artifact | Даже если GPT task задержался, repo не теряет ответ |
| 3 | Autoprocess result | Ответ Claude APPROVED / CHANGE_REQUIRED / BLOCKED автоматически фиксируется Codex task | Оператор не пересказывает результат |
| 4 | Agreement loop | CHANGE_REQUIRED запускает новый пакет Claude; APPROVED создаёт final protocol | Согласование должно идти до результата |
| 5 | Operator isolation | Оператор получает только финальный результат или high-risk выбор | Оператор не участвует в рабочем цикле |
| 6 | Evidence trail | Каждый шаг имеет SHA, state, report, proof | Нельзя писать PASS без доказательств |

## Дорожная карта

| Этап | Название | Что делаем | Acceptance | Статус | Обоснование |
|---|---|---|---|---|---|
| A0 | Зафиксировать проблему | Признать, что BEM-703 не имел подтвержденного recurring Task | Blocker записан; нет ложного PASS | ✅ частично | Это уже сделано BEM-705/BEM-707 |
| A1 | Task creation contract | Создать стандартный текст команды для recurring Task и правило PASS only with task-card | Файл протокола + handoff prompt + state | ✅ частично | BEM-702 есть, но нужен end-to-end proof |
| A2 | GPT-side recurring Task smoke | Создать recurring task `AI DevOps Claude mailbox monitor`; получить task-card/confirmation | В repo записан screenshot/text confirmation + scheduled interval | ⬜ | Это главный недостающий элемент |
| A3 | Scheduled run proof | Дождаться минимум 2 запусков recurring task | Есть два запуска с timestamp и результатом Deno healthCheck/mailbox check | ⬜ | Один запуск может быть случайным, нужно два |
| A4 | Mailbox fixture E2E | Положить синтетический Claude-response fixture в test mailbox и проверить, что monitor создаёт handoff/pending | Handoff + pending artifact созданы без оператора | ⬜ | Проверка pipeline без реального Claude решения |
| A5 | Real Claude response processing | Когда Claude ответит по BEM-703, task/Codex читает mailbox и фиксирует результат | Active agreement обновлен; next step создан | ⬜ | Это боевой proof |
| A6 | Agreement loop automation | Если CHANGE_REQUIRED — автоматически формируется новый пакет Claude; если APPROVED — final protocol | Создан final или next-round package | ⬜ | Согласование идёт до результата |
| A7 | No-operator audit | Проверить, что ни один routine step не требует оператора | Report показывает operator_role=none кроме final/high-risk | ⬜ | Требование оператора |
| A8 | Autonomy readiness report | Собрать финальный отчёт готовности автономности | Все criteria PASS с SHA/evidence | ⬜ | Финальное доказательство |

## Техническая схема

| Слой | Механизм | Роль | Статус |
|---|---|---|---|
| GPT-side wake-up | ChatGPT Scheduled Task | Будит GPT и запускает prompt проверки mailbox | не доказан |
| Repo-side fallback | curator-hourly-report.yml + check_claude_mailbox_alert.py | Фиксирует ответ Claude в repo-state/handoff, без оператора | частично готов |
| Execution | Deno /codex-task + codex-runner.yml | Записывает state/report/final artifacts | работает |
| Agreement state | governance/agreements/active/*.json | Хранит активные согласования | работает |
| Final results | governance/agreements/final/ | Хранит утвержденные протоколы | готово |

## Нельзя считать автономностью

| Ошибка | Почему нельзя |
|---|---|
| Repo request без task-card | Это не доказывает, что GPT проснётся |
| Telegram оператору | Это снова делает оператора relay |
| One-shot smoke вместо recurring | Не решает постоянный мониторинг |
| PASS без timestamp/SHA | Нарушает контракт |

## Следующее действие после утверждения roadmap
A2: создать/подтвердить recurring ChatGPT Task и провести 2-run proof. Roadmap implementation остаётся на паузе до команды оператора; разрешены только работы по автономности/согласованию.
