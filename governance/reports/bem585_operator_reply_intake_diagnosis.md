# BEM-585 | Operator Reply Intake Diagnosis

Дата: 2026-05-17 | 22:24 (UTC+3)

## Observation
Operator replied `1` in Telegram and received `HTTP 403`. Current decision was not proven as persisted in repo.

## Existing files
{
  "operator_decision_dispatcher": true,
  "operator_decision_pick": true,
  "operator_decision_record_dispatch": true,
  "operator_decision_queue": true,
  "operator_decisions": false,
  "telegram_outbox": true,
  "curator_workflow": true
}

## Diagnosis
Telegram outbound decision dispatcher exists, but inbound operator reply intake is not yet proven. Text reply `1/2/3` requires a handler or polling workflow that writes operator_decisions JSON.

## Required fix
Implement operator reply intake: get Telegram update, match active decision_id, create governance/operator_decisions/<decision_id>.json, then handoff to curator.

## Blocker
OPERATOR_REPLY_INTAKE_NOT_IMPLEMENTED_OR_FORBIDDEN
