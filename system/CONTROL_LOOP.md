# Autonomous Control Loop

This document defines the operational decision cycle of the AI DevOps agent.

The system operates as a continuous control loop that observes the system state,
analyzes conditions, decides actions, executes operations, and verifies results.

---

# Control Loop Stages

The agent must always operate using the following sequence:

1. OBSERVE
2. ANALYZE
3. DECIDE
4. ACT
5. VERIFY
6. BASELINE

The loop then repeats.

---

# 1. OBSERVE

The agent collects verified system state from trusted sources.

Sources include:

- Cloud Run service status
- deployment revision
- container image
- service URL
- environment configuration

All observations must come from **verified command outputs**.

Screenshots, memory, and assumptions are forbidden.

---

# 2. ANALYZE

The agent compares the observed runtime state with:

- expected architecture
- previous baseline
- deployment policies

The agent determines whether the system is:

- healthy
- degraded
- broken
- unknown

---

# 3. DECIDE

Based on analysis, the agent selects exactly one safe action.

Allowed actions include:

- verify deployment
- update configuration
- deploy new revision
- rollback to baseline
- collect additional state

The **One Action Rule** must always be respected.

---

# 4. ACT

The agent executes the selected action using controlled commands.

All actions must follow these principles:

- minimal change
- reversible operation
- explicit verification

No speculative actions are allowed.

---

# 5. VERIFY

After any action, the agent must verify the system state.

Verification includes:

- confirming service health
- validating revision deployment
- confirming service URL accessibility

If verification fails, the system enters **recovery mode**.

---

# 6. BASELINE

If the deployment is verified as stable, the agent may create a new baseline.

Baseline creation requires:

- successful deployment
- verified service health
- confirmed runtime state

The baseline becomes the new recovery point.

---

# Safety Principles

The control loop must always obey the following rules:

- One Action Rule
- Proof Only Rule
- No Guessing Rule
- Rollback First Strategy
