# Baseline Layer

The baseline layer stores the **last verified stable system state**.

A baseline represents a deployment that has been fully verified and
confirmed to be operational.

---

## Purpose

Baseline allows the system to:

- perform safe rollbacks
- track stable deployments
- restore known good configurations

---

## Baseline Contents

A baseline must contain:

- service name
- verified service URL
- stable revision
- container image
- deployment timestamp

---

## Baseline Rule

A new baseline may only be created when:

1. deployment completed
2. service health verified
3. runtime state confirmed

---

## Safety Principle

If a deployment fails, the system must rollback to the **last baseline**.
