# ARCHIVE MANIFEST
Дата архивации: 2026-05-01
Причина: переход на новый state layer (EXCHANGE.md + exchange.jsonl)

## Архивированные файлы

| Исходный путь | Новый путь | Причина |
|---|---|---|
| governance/exchange_ledger.csv | governance/archive/legacy-2026-05-01/exchange_ledger.csv | Заменён EXCHANGE.md + exchange.jsonl |

## Replacement в новой архитектуре

| Старый файл | Новый файл | Назначение |
|---|---|---|
| exchange_ledger.csv | governance/EXCHANGE.md | Человеко-читаемое состояние ISA |
| exchange_ledger.csv | governance/exchange.jsonl | Машинный журнал событий |

## Правила

1. Архив НЕ используется runtime/role workflows
2. Архив — только historical reference
3. Восстановление из архива только после owner approval
4. Активные промпты ролей не ссылаются на файлы из archive/
