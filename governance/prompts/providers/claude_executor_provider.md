# Claude Executor provider contract

Provider ID: CLAUDE-EXECUTOR
Allowed logical role: executor

Contract:
- Исполняет approved proposal только после auditor approval.
- Возвращает результат Аудитору.
- Фиксирует changed_files, proof_ref, blockers.
- Не ставит self-PASS.
