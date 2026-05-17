# BEM-558 | Active Curator Role — Operator Decision

Дата: 2026-05-17 | 18:09 (UTC+3)

## Решение оператора

| Наименование | Описание | Обоснование |
|---|---|---|
| Curator | Активная обязательная отдельная роль | Оператор уточнил: куратор тоже GPT/Codex |
| Curator provider | GPT/Codex only | Куратор не Claude и не абстрактный SYSTEM-gate |
| Analyst | Активная обязательная отдельная роль | BEM-557: аналитик всегда GPT/Codex |
| Auditor | Может быть Claude/GPT reserve | Аудитор отделён от куратора и аналитика |
| Executor | Может быть Claude/GPT/другой provider | Исполнитель отделён от куратора и аналитика |

## Обновлённая активная цепочка

External task -> Curator(GPT/Codex) -> Analyst(GPT/Codex) -> Auditor(Claude/GPT) -> Curator/System decision -> Executor(Claude/GPT/provider) -> Auditor final -> Curator closure.

## Запрет
GPT-agent не должен описывать Curator как пассивный gateway без provider. Curator — активная GPT/Codex роль.
