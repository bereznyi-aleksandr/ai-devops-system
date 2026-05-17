# BEM-548.6 | Contour Status Schema v2

Дата: 2026-05-17 | 15:10 (UTC+3)

## Назначение
Единый machine-readable dashboard для внешнего GPT, Claude и Telegram.

## Required sections
| Field | Meaning |
|---|---|
| schema_version | contour_status.v2 |
| updated_at | UTC+3 timestamp |
| roadmap | current roadmap progress |
| external_contour | GPT/Claude/Telegram status |
| internal_contour | curator/orchestrator/roles status |
| provider_contour | primary/reserve provider status |
| telegram | outbox/live delivery status |
| blockers | current blockers list |
| evidence | key SHA and report paths |
