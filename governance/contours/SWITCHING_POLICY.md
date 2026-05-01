# SWITCHING POLICY — Политика переключения контуров
Версия: v1.0 | Дата: 2026-05-01

## Основной контур
claude

## Резервный контур
gpt_codex

## Claude → GPT/Codex (переключение на fallback)

Условия (любое из):
1. Claude Code usage limit reached
2. Claude Code Action temporarily unavailable
3. Primary contour завис более одного часового цикла куратора
4. Владелец явно запросил fallback

Процесс:
1. GPT-куратор обнаруживает блокер в часовом цикле
2. Выдаёт BEM-отчёт с предложением fallback
3. Владелец подтверждает: "Разрешаю fallback"
4. Обновляется EXCHANGE.md: active_contour → gpt_codex
5. Добавляется событие в exchange.jsonl: CONTOUR_SWITCH
6. Запускается GPT_ANALYST

## GPT/Codex → Claude (возврат на primary)

Условия:
1. Claude Code снова доступен
2. Workflow проходит без ошибок
3. Нет активного блокера

Процесс:
1. GPT-куратор в очередном часовом цикле подтверждает доступность Claude
2. Выдаёт BEM-отчёт с предложением возврата
3. Владелец подтверждает
4. Обновляется EXCHANGE.md: active_contour → claude
5. Добавляется событие в exchange.jsonl: CONTOUR_SWITCH

## Запреты

1. Автоматическое переключение без owner approval — ЗАПРЕЩЕНО
2. Оба контура активны одновременно — ЗАПРЕЩЕНО
3. @analyst не запускает GPT_ANALYST
4. @codex ROLE=GPT_ANALYST не запускает Claude Analyst
