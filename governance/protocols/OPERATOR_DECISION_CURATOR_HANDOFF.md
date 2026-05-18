# BEM-593 | Operator Decision Curator Handoff

Дата: 2026-05-17 | 22:46 (UTC+3)

## Назначение

Любое решение оператора из `governance/operator_decisions/*.json` должно автоматически попадать куратору как machine-readable intake.

## Поток

operator_decisions JSON -> decision_curator_handoff.py -> governance/curator/inbox/operator_decision_<id>.json -> transport/results.jsonl -> curator/orchestrator.

## Правило

Оператор не переносит решение вручную. GPT/Actions фиксируют решение и передают куратору.
