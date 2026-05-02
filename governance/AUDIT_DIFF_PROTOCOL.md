# AUDIT DIFF PROTOCOL
Версия: v1.0 | Дата: 2026-05-01
Авторы: GPT-архитектор (BEM-147) + Claude-аудитор

---

## НАЗНАЧЕНИЕ

Протокол определяет как АУДИТОР проверяет изменения в репозитории.

Ключевое правило: аудитор проверяет только фактический diff конкретного commit или PR — не весь локальный checkout.

---

## ПРОБЛЕМА КОТОРУЮ РЕШАЕТ ЭТОТ ПРОТОКОЛ

Аудитор при проверке BEM-130 увидел в локальном checkout файлы из:
- `.github/workflows/` (legacy)
- `governance/archive/`
- `governance/quarantine/`

И сделал вывод что forbidden areas были затронуты.

Это была ошибка метода. Фактически BEM-130 изменил только два файла:
- `governance/EXCHANGE.md`
- `governance/exchange.jsonl`

Корневая причина: аудитор смотрел на весь checkout вместо commit diff.

---

## ПРАВИЛА АУДИТА ИЗМЕНЕНИЙ

### Шаг 1. Получить commit SHA или PR SHA
Источник: issue, комментарий исполнителя, state layer.

### Шаг 2. Получить список изменённых файлов

```bash
git diff --name-only <base_sha>..<head_sha>
```

Или через GitHub API:
```
GET /repos/{owner}/{repo}/commits/{sha}
→ смотреть files[].filename
```

### Шаг 3. Сравнить с approved scope
Сравнить список изменённых файлов с approved scope из вердикта.

### Шаг 4. Проверить forbidden areas
Проверять только touched files — не весь checkout.

Forbidden areas:
- `secrets` — любые файлы с credentials
- `billing` конфиги
- `permissions` файлы
- production deploy конфиги
- `.github/workflows/` — только если не в approved scope
- `governance/archive/` — только чтение, не запись

### Шаг 5. Вынести вердикт

```
VERDICT: APPROVED
или
VERDICT: BLOCKED: [конкретная причина]
```

---

## АБСОЛЮТНЫЕ ПРАВИЛА

| Правило | Статус |
|---|---|
| Проверять только commit diff или PR diff | ОБЯЗАТЕЛЬНО |
| Forbidden-area check только по touched files | ОБЯЗАТЕЛЬНО |
| Local checkout file list НЕ является доказательством нарушения scope | ЗАПРЕЩЕНО использовать |
| Если commit SHA недоступен — BLOCKED: missing commit evidence | ОБЯЗАТЕЛЬНО |
| Не делать предположения о затронутых файлах | ЗАПРЕЩЕНО |

---

## ДЛЯ STATE LAYER ИЗМЕНЕНИЙ

Автономный commit в `governance/EXCHANGE.md` и `governance/exchange.jsonl` допускается без owner approval если:
1. Изменяется только state layer
2. Нет затронутых secrets/billing/permissions/production
3. Есть явное событие в exchange.jsonl фиксирующее изменение

---

## ФОРМАТ АУДИТОРСКОГО ОТЧЁТА ПРИ ПРОВЕРКЕ ИЗМЕНЕНИЙ

```
AUDIT DIFF REPORT | BEM-XXX | дата

Commit SHA: <sha>
Touched files:
- file1
- file2

Approved scope: [из вердикта]

Forbidden areas check:
- secrets: NOT TOUCHED ✅
- billing: NOT TOUCHED ✅
- permissions: NOT TOUCHED ✅
- production: NOT TOUCHED ✅

VERDICT: APPROVED / BLOCKED
```

---

*Протокол принят: 2026-05-01 | BEM-147*
*Применяется к: всем аудиторским проверкам изменений файлов*
