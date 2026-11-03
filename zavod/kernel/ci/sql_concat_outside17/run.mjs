// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_outside17/run.mjs — цель пробы R15B-01: настоящий файл вне проверяемых
//   папок. Проба bad_flow17.mjs импортирует его по пути ../; проверка обязана отказать на импорте.
// ДАТА: 2026-11-02 15:09 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
export default (db, x) => db.query('SELECT ' + x);
