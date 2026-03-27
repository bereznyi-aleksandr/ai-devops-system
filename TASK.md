Измени файл .github/workflows/claude-agent.yml — только два изменения:

1. Добавь в секцию permissions строку:
   issues: write

2. Добавь триггер issues со следующей конфигурацией:
   issues:
     types: [opened, labeled]

3. В шаге Run Claude Code замени текущую команду на:
   if [ "${{ github.event_name }}" = "issues" ]; then
     TASK="${{ github.event.issue.body }}"
   else
     TASK="$(cat TASK.md)"
   fi
   claude --dangerously-skip-permissions -p "$TASK. После выполнения обнови PROGRESS.md записью о результате."

Больше ничего не меняй. Обнови PROGRESS.md и сделай коммит.
