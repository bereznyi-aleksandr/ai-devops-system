// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow15.mjs — проба 3.3.10.2 (аудит M3310-R14-03, -06, -07): примеры
//   аудитора — postgres.js sql.unsafe, execaCommand из стороннего пакета, свой объект с flatMap в списке запуска.
// ДАТА: 2026-11-02 10:25 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
import postgres from 'postgres';
import { execaCommand } from 'execa';
import { spawn } from 'node:child_process';
export async function run(sql, suppliedSql) { return sql.unsafe(suppliedSql); }
export async function go(command) { return execaCommand(command); }
export function start(line) {
  const x = { flatMap() { return line.split(' '); } };
  return spawn('docker', ['run', '--rm', 'image', ...x.flatMap(() => ['ok'])]);
}
export const client = postgres;
