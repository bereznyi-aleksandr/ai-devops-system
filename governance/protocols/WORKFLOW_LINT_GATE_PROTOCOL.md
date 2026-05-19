# BEM-693 | Workflow Lint-Gate Protocol

Дата: 2026-05-19 | 05:56 (UTC+3)

## Правила
1. Запрещён inline Python/heredoc в workflow YAML: `python3 - <<`, `python - <<`.
2. Любой `run: |` длиннее 8 значимых строк должен быть вынесен в `scripts/*.py`.
3. Workflow YAML должен только вызывать скрипты и передавать env/secrets, но не содержать сложную бизнес-логику.

## Обоснование
Большинство поломок были вызваны многострочным кодом внутри YAML. Логика в `scripts/*.py` проще проверяется через `python3 -m py_compile` и снижает риск invalid workflow.
