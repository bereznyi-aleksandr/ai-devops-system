# BEM-590 | Operator Decision Format Canon

Дата: 2026-05-17 | 22:37 (UTC+3)

## Operator decision

Operator selected option 1: `Короткая таблица`.

## Canonical Telegram format for operator decisions

1. BEM header.
2. Stage and roadmap percentages.
3. Checklist of what Claude/GPT prepared.
4. Clear question.
5. Mobile-readable comparison table with columns: `№`, `Вариант`, `Отличие / обоснование`.
6. Details block for long rationale/impact.
7. Auditor recommendation.
8. Reply instruction: `1 / 2 / 3 / own text`.

## Hard rule

Routine mailbox must not generate Telegram messages. Telegram operator decision must be generated only from structured decision package in `governance/operator_decision_queue/*.json`.

## Current limitation

Telegram text reply intake is implemented through workflow/poller, but HTTP 403 was observed in live chat. Chat fallback is allowed when operator choice is explicit.
