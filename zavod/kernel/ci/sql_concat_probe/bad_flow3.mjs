// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow3.mjs — проба карты 3.3.10.2 (аудит M3310-R3-01): вызов query
//   не через «.query(»: вычисляемое имя, псевдоним, bind/call, деструктуризация, имя в строке, eval; сборка обязана упасть.
// ДАТА: 2026-11-02 01:37 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
export async function computed(db, table) {
  const a = 'SEL';
  const b = 'ECT * FROM ';
  const sql = a + b + table;
  await db['query'](sql);
}
export async function optional(db, text) {
  await db.query?.(text);
}
export async function bound(db, sql) {
  const run = db.query.bind(db);
  await run(sql);
}
export async function destructured(db, sql) {
  const { query } = db;
  await query(sql);
}
export async function called(db, sql) {
  await db.query.call(db, sql);
}
export async function nameInString(db, sql) {
  const m = 'query';
  await db[m](sql);
}
export async function pieces(db, sql) {
  await db['qu' + 'ery'](sql);
}
export async function evaluated(db, sql) {
  await eval('db.query(sql)');
}
