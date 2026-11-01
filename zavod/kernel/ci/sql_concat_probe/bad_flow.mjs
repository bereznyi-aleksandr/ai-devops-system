// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow.mjs — проба карты 3.3.10.2 (аудит M3310-R1B-02): склейка через
//   переменные и куски; так писать нельзя, сборка обязана упасть.
// ДАТА: 2026-11-02 00:11 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
export async function appended(c, lease) {
  let q = 'SELECT * FROM bem_control.gate_command WHERE lease_id = ';
  q += lease;
  await c.query(q);
}
export async function throughName(c, lease) {
  const head = 'DELETE FROM bem_control.gate_command';
  const sql = head;
  await c.query(sql.concat(' WHERE lease_id = ', lease));
}
export async function pieces(c, table) {
  await c.query('SEL' + 'ECT * FROM ' + table);
}
export async function inTemplate(c, lease) {
  const base = 'SELECT * FROM bem_control.gate_command';
  await c.query(`${base} WHERE lease_id = 1`);
}
