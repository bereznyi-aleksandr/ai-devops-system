// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow5.mjs — проба карты 3.3.10.2 (аудит M3310-R5-01, -02, -03): примеры
//   аудитора и соседние пути к базе мимо «.query(постоянный текст)»; так писать нельзя, сборка обязана упасть.
// ДАТА: 2026-11-02 02:21 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
export async function rebound(db, k, table) {
  let holder = {};
  holder = db;
  const a = 'SEL', b = 'ECT * FROM ';
  const sql = a + b + table;
  await holder[k](sql);
}
const T = { run: () => 1 };
export async function shadowed(T, k, sql) {
  await T[k](sql);
}
export async function newlinePlus(db, table) {
  const suffix = 'ECT * FROM ';
  const sql = 'SEL'
    + suffix + table;
  await db.query(sql);
}
const fixed = 'SELECT 1';
export async function paramShadow(db, fixed) {
  await db.query(fixed);
}
export async function made(db, sql) {
  const make = (() => {}).constructor;
  const run = make('db', 'sql', 'return db.query(sql)');
  await run(db, sql);
}
export async function lowLayer(db, sql) {
  db.connection.parse({ text: sql });
  db.queryQueue.push(new db.Query(sql));
}
export async function harvested(db, sql) {
  const [c] = Object.values(db);
  await c.parse({ text: sql });
}
export function viaProcess(spawn, sql) {
  spawn(process.execPath, ['-e', sql]);
  spawn('psql', ['-c', sql]);
}
import vm from 'node:vm';
export const compiled = (code) => vm.runInThisContext(code);
const box = {};
export function protoSwap(db, a, b) { box[a] = db; return box[b]; }
