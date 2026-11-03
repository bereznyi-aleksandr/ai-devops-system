// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow4.mjs — проба карты 3.3.10.2 (аудит M3310-R4-01): имя query через
//   экранирование и другие пути вызвать метод базы мимо «.query(»; так писать нельзя, сборка обязана упасть.
// ДАТА: 2026-11-02 01:56 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
export async function escaped(db, table) {
  const a = 'SEL';
  const b = 'ECT * FROM ';
  const sql = a + b + table;
  await db['\u0071uery'](sql);
}
export async function escapedName(db, sql) {
  await db.\u0071uery(sql);
}
export async function otherEscapes(db, sql) {
  const k1 = '\x71uery';
  const k2 = `\u{71}uery`;
  await db[k1 + k2](sql);
}
export async function fixedKeyCall(db) {
  await db['select'.length > 0 ? 'q' : 'x'](sql);
}
export async function attached(db, k, sql) {
  db.run = db[k];
  await db.run(sql);
}
export async function attachedLiteral(db, k, sql) {
  const o = { ...db, run: db[k] };
  await o.run(sql);
}
export async function protoSwap(db, k, sql) {
  const o = Object.create(db);
  await o.run(sql);
}
export async function patternTarget(db, k, sql) {
  [db.run] = [db[k]];
  await db.run(sql);
}
export async function loopTarget(db, k, sql) {
  for (db.run of [db[k]]) await db.run(sql);
}
export async function computedName(db, k, sql) {
  const o = { [k]: 1 };
  await db[k].call(db, sql);
}
export async function reflected(db, k, sql) {
  await Reflect.apply(new Proxy(db, {}).run, db, [sql]);
}
export async function tagged(db, k) {
  await db[k]`SELECT 1`;
}
export async function loaded(src) {
  await import(src);
}
