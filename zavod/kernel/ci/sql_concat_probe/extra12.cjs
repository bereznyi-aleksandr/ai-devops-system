// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/extra12.cjs — проба (аудит M3310-R11-03): пример аудитора extra.cjs.
// ДАТА: 2026-11-02 07:26 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
module.exports=(db,x)=>db.query('SELECT '+x)
