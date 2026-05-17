# BEM-531.1 | Role Cycle State Schema

Дата: 2026-05-17 | 12:50 (UTC+3)

## Purpose
`governance/state/role_cycle_state.json` is the source of truth for the internal role cycle.

## Required fields
- schema_version
- updated_at
- cycle_id
- source
- curator_status
- active_role
- next_role
- current_task
- handoff
- agents
- agent_lifecycle
- history
- blocker

## Agent lifecycle
CANDIDATE -> ACTIVE -> RETIRED

Rules:
- CANDIDATE can be proposed but cannot execute.
- ACTIVE can receive role assignments.
- RETIRED cannot receive new assignments, but remains in history.

## Active roles
curator, analyst, auditor, executor.

## Backward compatibility
Legacy keys are preserved under `legacy.previous_keys` and history records.
