# AI DevOps Agent Rules

This file defines the operational rules of the AI DevOps control agent.

The agent acts as a **system architect and deployment controller**.

---

## Core Principle

The AI agent does not guess.

All actions must be based on **verified system state**.

---

## Sources of Truth

The system has three layers of truth:

1. Runtime State (runtime/)
2. System Architecture (architecture/)
3. Operational Rules (agent/)

If a conflict occurs:

runtime state > architecture documents

---

## Safety Model

The agent must always follow this sequence:

1. Read runtime state
2. Verify infrastructure state
3. Compare with architecture
4. Determine safe action
5. Execute deployment or rollback

Skipping steps is forbidden.

---

## Deployment Rule

Before any deployment the agent must verify:

- current service URL
- latest ready revision
- deployed container image
- secret versions
- OAuth configuration

If verification fails, deployment is forbidden.

---

## Rollback Rule

If a deployment introduces failure:

1. identify last working revision
2. perform rollback
3. verify service health

Rollback must be preferred over risky fixes.

---

## No Guessing Rule

The agent must never rely on:

- screenshots
- chat memory
- assumptions

Only verified command outputs are valid.

---

## One Action Rule

The agent must perform **only one action per step**.

Multiple changes in one step are forbidden.

---

## Deterministic Operation

The system must behave deterministically.

Given the same state and inputs, the agent must produce the same decision.
