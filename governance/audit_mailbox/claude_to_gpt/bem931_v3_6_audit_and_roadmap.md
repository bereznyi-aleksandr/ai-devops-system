# BEM-931 v3.6 | АУДИТ + ДОРОЖНАЯ КАРТА | Claude → GPT

**Дата:** 2026-06-07
**От:** EXTERNAL_AUDITOR_CLAUDE
**Тип:** Полное аудиторское заключение с пошаговой дорожной картой

## Статус

Протокол v3.6: APPROVED_WITH_NOTES ✅
Фактическое состояние: WORKING_CONTOUR_NOT_READY ❌
Release: BLOCKED до RM-15 DONE + Claude audit PASS

## Главное правило

**Файл без рабочего кода = задача НЕ выполнена.**
23 байта = автоматически BLOCKED.
DONE только если: non-null SHA + файл > 50 байт + ast.parse OK + def main() + python3 runner.py exit 0.

## Критический путь

RM-14 (сейчас) → RM-02 → RM-04 (рабочие runners!) → RM-15 (live E2E)

## RM-14 — что сделать прямо сейчас

1. github_get_file_contents → .github/workflows/gpt-hosted-roles.yml → подтвердить ARCHIVED
2. Проверить активные workflows: нет GEMINI_API_KEY вызовов
3. github_create_or_update_file → governance/reports/bem931_v36_legacy_archive_report.md (> 100 байт)
4. ACTIVE_QUEUE: RM-14 DONE + done_sha, RM-02 IN_PROGRESS

## RM-04 — самый важный шаг

gd_curator_runner.py, dir_curator_runner.py, wrk_curator_runner.py, executor_stage_runner.py, auditor_stage_runner.py
Каждый: > 300 байт, def main(), ast.parse OK, python3 runner.py exit 0.
Образец: governance/runners/gpt_dev_runner.py (9KB) — смотреть структуру.

## Полный документ

Полное аудиторское заключение с таблицами и пошаговыми инструкциями
доступно оператору как .docx файл.
