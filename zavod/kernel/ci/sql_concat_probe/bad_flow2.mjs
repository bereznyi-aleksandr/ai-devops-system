// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow2.mjs — проба карты 3.3.10.2 (аудит M3310-R2-01): текст запроса
//   из массива через .join(), из функции, из параметра и через обёртку; так писать нельзя, сборка обязана упасть.
// ДАТА: 2026-11-02 01:15 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
export async function joined(db, table) {
  const sql = ['SELECT * FROM ', table].join('');
  await db.query(sql);
}
function pick(kind) {
  return kind === 'all' ? 'SELECT * FROM bem_control.gate_command' : 'SELECT 1';
}
export async function fromFunction(db, kind) {
  await db.query(pick(kind), []);
}
export async function fromParam(db, text) {
  await db.query(text);
}
export async function throughWrapper(db, table) {
  const one = async (sql) => (await db.query(sql)).rows;
  await one('SELECT 1');
  return one(['SELECT * FROM', table].join(' '));
}
