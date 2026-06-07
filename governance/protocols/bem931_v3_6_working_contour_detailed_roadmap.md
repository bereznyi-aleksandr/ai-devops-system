# BEM-931 v3.6 — рабочий управляющий контур

Статус: проект протокола для согласования оператором.
Основание: BEM-931 v3.5. В v3.5 зафиксированы GD/DIR/WRK, WRK-C1..WRK-C3, Codex Local как штатный runtime, curator-mediated exchange, RM-12 как gate после RM-01..RM-11.
Фактический статус: WORKING_CONTOUR_NOT_READY.
Главное правило: задача считается закрытой только подтверждённым результатом, trace/receipt, валидатором и каноническим отчётом. Файл без runtime-доказательства не закрывает задачу.

## 1. Каноническая структура

Объекты:
- GD: GD.CURATOR + GD-C1, GD-C2.
- DIR: DIR.CURATOR + DIR-C1, DIR-C2.
- WRK: WRK.CURATOR + WRK-C1, WRK-C2, WRK-C3 минимум, расширение до WRK-CN.

Каждый внутренний контур состоит из:
- ANALYST;
- AUDITOR;
- EXECUTOR.

Минимальный набор элементов:
- 3 куратора: GD.CURATOR, DIR.CURATOR, WRK.CURATOR.
- 7 внутренних контуров * 3 роли = 21 роль.
- Итого минимум 24 элемента.

Канонический маршрут внутри контура:
curator -> analyst -> auditor pre-check -> executor -> auditor post-check -> curator.

Канонический внешний маршрут:
operator -> GD.CURATOR -> DIR.CURATOR -> WRK.CURATOR -> WRK-Cx -> WRK.CURATOR -> DIR.CURATOR -> GD.CURATOR -> operator.

## 2. Статусы

PENDING — не начато.
IN_PROGRESS — выполняется.
DONE_REPO — файлы и валидаторы созданы.
DONE_RUNTIME — роль реально запущена через Codex provider и дала trace.
DONE_LIVE — подтверждён живой Telegram/Codex/GitHub Actions проход.
BLOCKED — есть блокер.
FAILED — закрытие было ошибочным.

Запрещено ставить DONE_RUNTIME или DONE_LIVE по факту записи файла.

## 3. Дорожная карта v3.6

| Этап | Название | Задач | Приёмка этапа |
|---:|---|---:|---|
| RM-01 | Очистка ложного статуса | 5 | WORKING_CONTOUR_NOT_READY зафиксирован, старое закрытие помечено недействительным для runtime |
| RM-02 | Канонические паспорта объектов | 8 | GD/DIR/WRK имеют паспорта; WRK-C1..WRK-C3 не смешаны с ролями |
| RM-03 | Реестр внутренних контуров | 7 | GD-C1/GD-C2/DIR-C1/DIR-C2/WRK-C1/WRK-C2/WRK-C3 созданы как контуры |
| RM-04 | Реестр элементов | 14 | 24 элемента созданы; каждый элемент имеет contour_id, prompt_profile_id, provider_binding_id |
| RM-05 | Правила и rule_version | 9 | rule_id/rule_version/scope/owner/status обязательны; наследование правил валидируется |
| RM-06 | Промпты и профили элементов | 16 | у каждой роли и каждого элемента есть профиль, dynamic_refs с rule_version |
| RM-07 | Provider bindings | 15 | каждый элемент привязан к codex-local; Gemini/API/paid hosted запрещены |
| RM-08 | Managed channels и маршруты | 11 | нет прямых runtime-связей роль-роль между контурами |
| RM-09 | Оркестрация ролей | 13 | dispatcher запускает конкретный element_id через Codex Local |
| RM-10 | Горизонтальный обмен | 9 | обмен идёт через куратора, proof_ref, data_version, rule_version |
| RM-11 | Telegram и канон отчёта | 9 | отчёты читаемые: проценты этапа, проценты дорожной карты, чек-лист, вопрос |
| RM-12 | Return path и внешний аудит | 9 | operator direct report; GPT/Claude через mailbox + wake-up |
| RM-13 | Ошибка -> опыт -> правило | 8 | ошибка создаёт experience и при необходимости новую rule_version |
| RM-14 | Архив legacy runtime | 8 | legacy Gemini/API/paid hosted не имеет active triggers |
| RM-15 | Live E2E одного контура | 13 | operator -> GD -> DIR -> WRK -> WRK-C1 -> operator проходит live |
| RM-16 | Live E2E нескольких WRK-контуров | 7 | WRK-C1/WRK-C2/WRK-C3 работают изолированно |
| RM-17 | Live горизонтальный обмен | 6 | WRK-C2 получает verified artifact от WRK-C1 через куратора |
| RM-18 | Release gate | 11 | все receipts собраны, Claude audit получен, RELEASE_PASS разрешён |

Итого: 178 задач.

## 4. Детализация этапов

### RM-01. Очистка ложного статуса
1. Создать verdict previous_closure_invalid_for_runtime.
2. Зафиксировать WORKING_CONTOUR_NOT_READY.
3. Разделить repo/runtime/live уровни.
4. Создать gap report.
5. Заблокировать RM-18 до PASS RM-01..RM-17.

### RM-02. Канонические паспорта объектов
1. objects_registry_v2.json.
2. object_passports/GD.json.
3. object_passports/DIR.json.
4. object_passports/WRK.json.
5. Убрать WRK.ANALYSIS_CONTOUR/WRK.AUDIT_CONTOUR/WRK.EXECUTION_CONTOUR как ошибочные контуры.
6. Добавить WRK-CN policy.
7. Прописать rule_owner каждого объекта.
8. Валидатор паспортов.

### RM-03. Реестр внутренних контуров
1. contours_registry.json.
2. GD-C1 и GD-C2.
3. DIR-C1 и DIR-C2.
4. WRK-C1, WRK-C2, WRK-C3.
5. object_id для каждого контура.
6. role_set analyst/auditor/executor для каждого контура.
7. state_path и managed_channel_id для каждого контура.

### RM-04. Реестр элементов
1. elements_registry_v2.json.
2. GD.CURATOR.
3. DIR.CURATOR.
4. WRK.CURATOR.
5. Роли GD-C1.
6. Роли GD-C2.
7. Роли DIR-C1.
8. Роли DIR-C2.
9. Роли WRK-C1.
10. Роли WRK-C2.
11. Роли WRK-C3.
12. prompt_profile_id у каждого элемента.
13. provider_binding_id у каждого элемента.
14. Валидатор elements->contours.

### RM-05. Правила
1. rule_registry_v2.json.
2. GD system rules.
3. DIR inherited rules.
4. WRK inherited rules.
5. rule inheritance graph.
6. rule conflict policy.
7. rule cache invalidation.
8. validator rule_version.
9. validator inheritance.

### RM-06. Промпты
1. role prompt curator.
2. role prompt analyst.
3. role prompt auditor.
4. role prompt executor.
5. profile GD.CURATOR.
6. profiles GD-C1.
7. profiles GD-C2.
8. profile DIR.CURATOR.
9. profiles DIR-C1.
10. profiles DIR-C2.
11. profile WRK.CURATOR.
12. profiles WRK-C1.
13. profiles WRK-C2.
14. profiles WRK-C3.
15. validator elements->profiles.
16. validator profiles->rule_version.

### RM-07. Providers
1. provider_registry.json.
2. codex_local active.
3. Gemini/API/paid hosted forbidden.
4. bindings for all 24 elements.
5. codex-local health check.
6. self-hosted runner online receipt.
7. Codex CLI receipt.
8. provider binding validator.
9. live provider receipt schema.

### RM-08. Managed channels
1. managed_channels_registry.json.
2. task envelope schema.
3. message state machine.
4. claim-lock.
5. operator->GD.CURATOR route.
6. GD.CURATOR->DIR.CURATOR route.
7. DIR.CURATOR->WRK.CURATOR route.
8. WRK.CURATOR->WRK-Cx.ANALYST route.
9. AUDITOR->CURATOR feedback route.
10. no direct role-to-role validator.
11. routes validator.

### RM-09. Orchestration
1. role-dispatch workflow.
2. codex-local receives element_id.
3. codex-local receives prompt_profile.
4. codex-local receives rule_version refs.
5. curator dispatch.
6. analyst plan artifact.
7. auditor pre-check.
8. executor result artifact.
9. auditor post-check.
10. curator final report.
11. trace builder.
12. fail-closed role error handling.
13. orchestration validator.

### RM-10. Horizontal exchange
1. exchange_registry_v2.json.
2. receiver contour -> curator request.
3. curator -> sender contour request.
4. verified artifact from sender auditor.
5. receiver analyst intake.
6. exchange proof receipt.
7. no-direct-horizontal validator.
8. live WRK-C1->WRK-C2 exchange.
9. live DIR-C1->WRK-C1 exchange.

### RM-11. Telegram
1. notification policy.
2. telegram outbox formatter.
3. hourly report formatter.
4. task report formatter.
5. validator: no diff/stdout/stderr/traceback.
6. live operator command receipt.
7. live hourly report receipt.
8. live task completion receipt.
9. mobile readability receipt.

### RM-12. Return path
1. return_path_registry_v2.json.
2. operator direct report.
3. GPT mailbox + wake-up.
4. Claude mailbox + wake-up.
5. curator internal return.
6. mailbox schema.
7. wake-up formatter.
8. live GPT mailbox test.
9. live Claude mailbox test.

### RM-13. Error -> experience -> rule
1. error_log_v2.jsonl.
2. experience_registry_v2.json.
3. rule proposal schema.
4. auditor classification.
5. rule update workflow.
6. dynamic refs refresh.
7. live report-error-to-rule test.
8. error-to-rule validator.

### RM-14. Legacy archive
1. workflow inventory.
2. find Gemini/API/paid hosted paths.
3. disable automatic triggers.
4. mark deprecated.
5. gpt-hosted-roles disabled stub.
6. Gemini secrets not used in active runtime.
7. legacy disabled validator.
8. codex-local regression validator.

### RM-15. Live E2E one contour
1. Telegram task from operator.
2. GD.CURATOR live receipt.
3. DIR.CURATOR live receipt.
4. WRK.CURATOR chooses WRK-C1.
5. WRK-C1.ANALYST plan.
6. WRK-C1.AUDITOR pre-check.
7. WRK-C1.EXECUTOR result.
8. WRK-C1.AUDITOR post-check.
9. WRK.CURATOR result receipt.
10. DIR.CURATOR result receipt.
11. GD.CURATOR result receipt.
12. Operator canonical report message_id.
13. live E2E validator.

### RM-16. Multi-contour live
1. Live WRK-C1.
2. Live WRK-C2.
3. Live WRK-C3.
4. state isolation validator.
5. prompt profile isolation validator.
6. result path isolation validator.
7. multi-contour receipt.

### RM-17. Horizontal live exchange
1. WRK-C2 requests artifact from WRK-C1.
2. WRK-C1 auditor verifies source.
3. WRK-C2 analyst receives artifact.
4. exchange_registry records proof/data/rule version.
5. validator rejects direct role-to-role.
6. operator summary report.

### RM-18. Release gate
1. collect all receipts RM-01..RM-17.
2. full validation pack.
3. self-hosted runner online proof.
4. Codex CLI proof.
5. Telegram readability proof.
6. Claude audit proof.
7. no paid API proof.
8. no active legacy triggers proof.
9. GD.CURATOR release decision.
10. final operator report.
11. set RELEASE_PASS only after all above PASS.

## 5. Правила приёмки

Задача закрывается только при наличии:
- SHA;
- результата;
- trace или receipt;
- валидатора;
- execution_log;
- канонического отчёта;
- отсутствия блокеров.

Runtime-задача дополнительно требует:
- Codex provider receipt;
- trace конкретного element_id;
- role result;
- auditor acceptance;
- fail-closed проверку.

Live-задача дополнительно требует:
- Telegram message_id;
- GitHub Actions run id;
- self-hosted runner receipt;
- external audit receipt, если задача влияет на release.

## 6. Канон отчёта оператору

Только:
1. Этап: задачи этапа X/Y (%).
2. Дорожная карта: этапы X/Y (%).
3. Чек-лист отдельными строками.
4. Вопрос оператору, если есть.

Запрещено:
diff, stdout, stderr, traceback, raw json, длинные технические логи, рассуждения вместо статуса.

## 7. Финальный критерий готовности

Контур готов только когда live trace подтверждает:
operator -> GD.CURATOR -> DIR.CURATOR -> WRK.CURATOR -> WRK-Cx.ANALYST -> WRK-Cx.AUDITOR -> WRK-Cx.EXECUTOR -> WRK-Cx.AUDITOR -> WRK.CURATOR -> DIR.CURATOR -> GD.CURATOR -> operator.

До этого статус: WORKING_CONTOUR_NOT_READY.
