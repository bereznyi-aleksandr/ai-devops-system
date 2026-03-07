# Runtime State

This file represents the verified operational state of the system.

The runtime layer is the **real environment state**, not documentation.

It records information verified directly from infrastructure.

---

## Service State

Service Name:
barber-app

Environment:
staging

Deployment Platform:
Google Cloud Run

---

## Verification Sources

The runtime state must only be updated using verified system outputs:

- gcloud run services describe
- gcloud run revisions list
- Secret Manager
- direct HTTP checks (curl)

Screenshots or assumptions are not valid sources.

---

## State Principles

Runtime state must always reflect:

- latest ready revision
- deployed image
- service URL
- operational status

If the runtime state differs from the architecture documents,
**runtime state is the source of truth**.

---

## Safety Rule

No deployments may occur without verifying runtime state.

Runtime verification must happen before:

- deploy
- rollback
- secret rotation
- OAuth changes
