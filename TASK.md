Измени файл .github/workflows/claude-agent.yml

Добавь второй триггер issues с типами opened и labeled.

Логика выбора задачи:
- если триггер от issue используй github.event.issue.body как задачу
- если триггер от push TASK.md используй cat TASK.md

После выполнения задачи:
- пиши результат в PROGRESS.md
- добавь комментарий к issue через GitHub API с результатом
- закрой issue через GitHub API

Обнови PROGRESS.md записью о старте E3 и сделай коммит.
