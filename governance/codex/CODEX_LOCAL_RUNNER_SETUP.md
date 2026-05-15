# Codex Local Runner Setup

**BEM-495** | Версия: v1.0 | 2026-05-15

Это инструкция по установке self-hosted runner с Codex CLI для контура:

```
ChatGPT → Deno /codex-task → codex-runner.yml → [self-hosted, codex-local] → Codex CLI
```

---

## 1. Добавить runner в GitHub

**GitHub UI:**
```
Repo → Settings → Actions → Runners → New self-hosted runner
```

**Выбери OS** (Linux рекомендован):
- Скачай и установи runner agent по инструкции GitHub.
- Во время `./config.sh` добавь label:

```bash
# Когда спросит "Enter any additional labels":
codex-local
```

Итоговые labels: `self-hosted`, `codex-local` (оба обязательны).

---

## 2. Установить зависимости

### Node.js через nvm

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc   # или ~/.zshrc
nvm install 24
nvm use 24
node -v
```

### Codex CLI

```bash
npm install -g @openai/codex
codex --version
```

> Убедись, что `OPENAI_API_KEY` доступен как переменная окружения или в конфиге Codex.

### Git

```bash
git --version   # должен быть установлен
```

---

## 3. Проверки перед запуском

```bash
# Codex CLI доступен
codex --version

# Node доступен
node -v

# Git настроен
git config --global user.email "codex-runner@ai-devops-system"
git config --global user.name "Codex Runner"

# Токен доступен (PAT должен быть в repo secrets как AI_SYSTEM_GITHUB_PAT)
echo "Secrets are managed by GitHub Actions — not stored locally."
```

---

## 4. Запустить runner

### Разово (для теста)

```bash
cd ~/actions-runner
./run.sh
```

### Как systemd service (продакшн)

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

---

## 5. Остановить runner

```bash
# Если запущен разово:
Ctrl+C

# Если как service:
sudo ./svc.sh stop
sudo ./svc.sh uninstall
```

---

## 6. Проверка что runner online

**GitHub UI:**
```
Repo → Settings → Actions → Runners → видишь "Idle" (зелёный)
```

---

## 7. Self-test после запуска

После появления runner online запустить через Deno:

```
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/codex-task?trace_id=bem495_codex_local_selftest&task_type=selftest&title=Codex+Local+Selftest&objective=Create+governance/codex/proofs/bem495_codex_local_selftest.txt+and+write+result.+No+issue+comments.

Мониторинг:
GET https://fine-chicken-23.bereznyi-aleksandr.deno.net/codex-status?trace_id=bem495_codex_local_selftest
```

**PASS если:**
- `codex --version` прошёл
- `governance/codex/proofs/bem495_codex_local_selftest.txt` создан
- `governance/codex/results/bem495_codex_local_selftest.json` создан со `status=completed`
- `/codex-status` возвращает `status=completed, proof_exists: true`

---

## 8. Что НЕ делать

- ❌ Не публиковать `OPENAI_API_KEY` или `AI_SYSTEM_GITHUB_PAT` в файлы репозитория
- ❌ Не писать в issue #31 комментарии (заблокирован на 2500 limit)
- ❌ Не включать `schedule` triggers в workflow файлах
- ❌ Не запускать runner с root правами
- ❌ Не хранить секреты в `.env` файлах в репозитории

---

## 9. Архитектура контура

```
ChatGPT (open URL)
  → Deno GET /codex-task?trace_id=X&task_type=selftest&...
      → создаёт governance/codex/tasks/X.json
      → workflow_dispatch codex-runner.yml (inputs: trace_id=X)
          → job runs-on: [self-hosted, codex-local]
              → codex --version (verify)
              → reads governance/codex/tasks/X.json
              → codex exec "<task prompt>"
              → commits changed files
              → writes governance/codex/results/X.json + X.md
  → ChatGPT (open URL)
  → Deno GET /codex-status?trace_id=X
      → reads governance/codex/results/X.json
      → returns status/blocker/commit_sha
```

---

## 10. Blockers и их значение

| Blocker code | Причина | Решение |
|---|---|---|
| `SELF_HOSTED_RUNNER_OFFLINE` | runner не поднят или остановлен | Запустить `./run.sh` или `sudo ./svc.sh start` |
| `CODEX_CLI_NOT_AVAILABLE` | codex не установлен на runner | `npm install -g @openai/codex` |
| `TASK_FILE_NOT_FOUND` | Deno не создал task file | Проверить `/codex-task` response — должен быть `task_write_status: 200/201` |
| `CODEX_EXEC_FAILED` | codex вернул ненулевой exit | Проверить job summary — там raw output Codex |
