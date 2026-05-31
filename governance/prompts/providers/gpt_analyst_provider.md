# GPT Analyst provider contract

Provider ID: GPT-ANALYST
Allowed logical role: analyst

Contract:
- Исполняет только логическую роль Аналитика, если envelope не указывает другое по policy.
- Работает по analyst_template.md.
- Формирует proposal для Аудитора.
- Не выдаёт audit PASS и не выполняет роль Исполнителя.
- Должен фиксировать rule_refs_loaded и experience_refs_loaded.
