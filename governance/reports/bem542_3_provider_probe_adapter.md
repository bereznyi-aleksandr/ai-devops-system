# BEM-542.3 | Provider Probe Before Reserve | PASS

Дата: 2026-05-17 | 14:15 (UTC+3)

## Что проверено
Provider adapter не переключает молча на GPT reserve. Сначала фиксируется provider probe.

| Probe signal | Selected provider | Reserve used | Обоснование |
|---|---|---|---|
| active | claude | False | Claude доступен, reserve запрещён |
| failed | gpt | True | Claude failed, reserve разрешён |

## Blocker
null
