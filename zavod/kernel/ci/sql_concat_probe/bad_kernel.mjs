// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_kernel.mjs — проба карты 3.3.10.2: так писать нельзя, сборка обязана упасть.
// ДАТА: 2026-11-01 22:56 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
export async function read(c, lease) {
  await c.query(`SELECT * FROM bem_control.gate_command WHERE lease_id = '${lease}'`);
  await c.query('DELETE FROM bem_control.gate_command WHERE lease_id = ' + lease);
}
