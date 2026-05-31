# Dispatch consumer contract

Назначение: обрабатывать очередь задач и запускать provider-aware lifecycle.

Contract:
- Читать queued items.
- Валидировать schema, policy, dependencies.
- Назначать target_object, target_contour, logical_role, provider_id.
- Писать event_log transitions.
- Не ставить completed без proof_ref.
- Возвращать operator_gate при policy/gate блокерах.
