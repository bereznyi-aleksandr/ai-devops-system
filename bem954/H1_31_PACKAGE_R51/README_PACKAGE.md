# Пакет H1_31_PACKAGE_R51

Документ: `101_CLAUDE_ARCHITECT_PROPOSAL_H1_31_R51_v1_31.md`, SHA-256 `d653f8f5653c61c5a81385d788a67fbf9b4451556f028df7456007ad96eec05c`.

## Как проверить и пересобрать

Команды запускаются из этой папки. Node — любой версии не ниже 20.

```text
node verify_package.mjs "<путь к H1.31>" --expect-edition H1.31
node build_package.mjs "<путь к H1.31>" --expect-edition H1.31 --pg16-evidence EVIDENCE_PG16_D05.txt
node build_package.mjs "<путь к H1.31>" --expect-edition H1.31 --pg16-evidence EVIDENCE_PG16_D05.txt --out "<новая пустая папка>"
```

Первая команда — независимая проверка: состав папки против описи,
суммы, строки, листинги документа против файлов и чистая повторная
сборка во временную папку с побайтной сверкой. Вторая — пересборка на
месте: сборщик ничего не перезаписывает, и любое расхождение с
документом — отказ. Третья собирает пакет заново в пустую папку.

Набор подделок кладёт копии документа во временную папку системы, а
не сюда; другая папка задаётся ключом `--work`.

## Состав

Список ниже сверяет `verify_package.mjs`: он обязан совпасть с описью
`package_manifest.json`, с полем `files` отчёта `package_report.json` и с
фактической папкой — до имени.

```text
BEM954-PACKAGE-FILES-BEGIN
00_cluster_bootstrap.sql
01_database_migration.sql
02_upgrade_to_h110.sql
03_restore_verifier.sql
04_backup_window.sql
05_final_state_check.sql
EVIDENCE_PG16_D05.txt
README_PACKAGE.md
bem954_registry_check.mjs
bem954_semantic_check.mjs
build_package.mjs
chk_round_facts.mjs
chk_tamper28.mjs
migration_manifest.json
package_manifest.json
package_report.json
pkg_extract.mjs
run_migration.mjs
tamper_manifest28.mjs
tamper_report.json
verify_package.mjs
BEM954-PACKAGE-FILES-END
```

## Чего пакет не доказывает

Сборка и проверка доказывают целостность и связность пакета, а не
поведение базы. Единственная улика живого прогона внутри пакета —
`EVIDENCE_PG16_D05.txt` (проверка D-05 на PostgreSQL 16.15); сборщик
принимает её, только если она называет этот документ и этот файл 01.
Остальные живые прогоны (чистая установка, повтор, файл 03, окно
копирования, путь 02 + 01 с формы H1.6) выполняются после сборки и
описываются отдельным отчётом раунда с журналами и суммами.
