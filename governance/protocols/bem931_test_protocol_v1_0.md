# ПРОТОКОЛ ТЕСТИРОВАНИЯ УПРАВЛЯЮЩЕГО КОНТУРА
# BEM-931-TEST-v1.0 | 2026-06-08
# Для исполнения: EXTERNAL_AUDITOR_GPT
# Назначение: верифицировать что управляющий контур работает как РЕАЛЬНАЯ система,
# а не как симуляция внутри одного Python процесса

---

## ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ ДЛЯ GPT

Текущие receipts (github_run_id: 27116441198) доказывают что:
✅ Python runners выполняются без ошибок
✅ Файловые каналы создаются правильно
✅ GitHub Actions запускается и коммитит файлы

Но они НЕ доказывают:
❌ Что Telegram-сообщение от оператора проходит через контур
❌ Что GD.CURATOR реально принимает задачи из Telegram
❌ Что система работает как автономная — без ручного запуска workflow
❌ Что WRK-C1/C2/C3 выбираются динамически под задачу, а не жёстко зашиты

---

## ТЕСТ T-01: ПРЯМОЙ ЗАПУСК ЦЕПОЧКИ ЧЕРЕЗ GITHUB ACTIONS

**Цель:** Убедиться что runners работают в GitHub Actions окружении
**Статус:** ✅ ДОКАЗАНО (run_id 27116441198)
**Метод:** bem931_live_receipt_proof.py запускает runners последовательно
**Acceptance:** receipt в governance/proofs/ с реальным GITHUB_RUN_ID

| Проверка | Результат |
|---|---|
| gd_curator_runner.py exit 0 | ✅ PASS |
| dir_curator_runner.py exit 0 | ✅ PASS |
| wrk_curator_runner.py exit 0 | ✅ PASS |
| analyst_stage_runner.py exit 0 | ✅ PASS |
| auditor_stage_runner.py exit 0 | ✅ PASS |
| executor_stage_runner.py exit 0 | ✅ PASS |
| WRK-C1 изолированный проход | ✅ PASS |
| WRK-C2 изолированный проход | ✅ PASS |
| WRK-C3 изолированный проход | ✅ PASS |
| Горизонтальный обмен через куратора | ✅ PASS |

---

## ТЕСТ T-02: TELEGRAM → КОНТУР → TELEGRAM (END-TO-END РЕАЛЬНЫЙ)

**Цель:** Убедиться что оператор может написать боту и получить ответ через контур
**Статус:** ❌ НЕ ПРОТЕСТИРОВАН
**Метод:**
1. Оператор пишет в Telegram боту: "запусти тест контура"
2. telegram-poll.yml читает сообщение → диспатчит workflow
3. GD.CURATOR принимает задачу из inbox
4. Цепочка GD→DIR→WRK→WRK-C1→ANALYST→AUDITOR→EXECUTOR→AUDITOR
5. GD.CURATOR пишет ответ оператору в Telegram

**Acceptance:**
- Telegram message_id входящего сообщения зафиксирован
- Telegram message_id ответного сообщения зафиксирован
- Между ними — полный trace_id в channels

**Задача для GPT:**
```
1. Убедиться что telegram-poll.yml активен (не DISABLED)
2. Убедиться что при получении сообщения диспатчится workflow с role=curator
3. Убедиться что curator после выполнения пишет ответ в Telegram
4. Оператор пишет тестовое сообщение боту
5. Зафиксировать результат в governance/proofs/BEM931-TEST-T02_telegram_e2e.json
```

---

## ТЕСТ T-03: САМОПОСТАНОВКА ЗАДАЧИ (SCHEDULER)

**Цель:** Убедиться что система продолжает работать без вмешательства оператора
**Статус:** ❌ НЕ ПРОТЕСТИРОВАН
**Метод:**
1. Поместить тестовую задачу в governance/channels/operator_to_gd.jsonl
2. Подождать 5 минут (cron scheduler)
3. Проверить что задача прошла цепочку без ручного dispatch

**Acceptance:**
- trace_id из задачи появился в gd_to_dir.jsonl, dir_to_wrk.jsonl, wrk_c1_to_analyst.jsonl
- worker_result.json создан
- Без ручного workflow_dispatch

---

## ТЕСТ T-04: АВТОРЕМОНТ (FAULT INJECTION)

**Цель:** Убедиться что система восстанавливается после ошибки
**Статус:** ❌ НЕ ПРОТЕСТИРОВАН
**Метод:**
1. Намеренно сломать один runner (добавить raise Exception в начало)
2. Запустить цепочку
3. Проверить что система зафиксировала ошибку в blockers/
4. Восстановить runner
5. Повторить запуск — цепочка проходит

**Acceptance:**
- blockers/ содержит запись об ошибке с trace_id
- После восстановления — цепочка проходит полностью

---

## ТЕКУЩИЙ ЧЕСТНЫЙ СТАТУС СИСТЕМЫ

| Компонент | Статус | Доказательство |
|---|---|---|
| Runners — синтаксис и логика | ✅ РАБОЧИЕ | ast.parse OK, exit 0 |
| GitHub Actions CI | ✅ РАБОТАЕТ | run_id 27116441198 |
| Файловые каналы (jsonl) | ✅ РАБОТАЮТ | channels/ создаются |
| Scheduler cron 5min | ⚠️ ЕСТЬ В WORKFLOW | Не проверен live |
| Telegram → контур | ❌ НЕ ПРОВЕРЕН | T-02 не выполнен |
| Контур → Telegram | ❌ НЕ ПРОВЕРЕН | T-02 не выполнен |
| Авторемонт при сбое | ❌ НЕ ПРОВЕРЕН | T-04 не выполнен |

---

## ПОРЯДОК ВЫПОЛНЕНИЯ ДЛЯ GPT

1. T-02 (Telegram E2E) — выполнить первым. Это главная проверка.
2. T-03 (Scheduler) — после T-02
3. T-04 (Fault injection) — после T-03
4. После всех тестов — записать сводный receipt в governance/proofs/BEM931-TEST-COMPLETE.json
5. Передать оператору итог через Telegram

---

## ФОРМАТ RECEIPT ДЛЯ КАЖДОГО ТЕСТА

```json
{
  "test_id": "T-02",
  "protocol": "BEM-931-TEST-v1.0",
  "status": "PASS",
  "github_run_id": "<реальный run_id>",
  "telegram_input_message_id": "<id входящего>",
  "telegram_output_message_id": "<id ответного>",
  "trace_id": "<trace из channels>",
  "created_at": "<timestamp>"
}
```

---

*Протокол подготовлен: Claude (EXTERNAL_AUDITOR_CLAUDE) | 2026-06-08*
*Записать в: governance/protocols/bem931_test_protocol_v1_0.md*
