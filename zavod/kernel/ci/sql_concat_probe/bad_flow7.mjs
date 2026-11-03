// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow7.mjs — проба карты 3.3.10.2 (аудит M3310-R7-01, -02): пример
//   аудитора и соседние пути: список, изменённый через обратный вызов или this; сценарий оболочки, исполняющий аргументы.
// ДАТА: 2026-11-02 03:47 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import { spawn, spawnSync } from 'node:child_process';
export function alias(db, sql) {
  const names = ['safe'];
  names.forEach((_, i, a) => { a[0] = 'qu' + 'ery'; });
  for (const k of names) db[k](sql);
  const two = ['safe'];
  two.map(function (k) { this[0] = 'x'; return k; }, two);
  for (const k of two) db[k](sql);
  const three = ['safe'];
  three.push.call(three, 'x');
  for (const k of three) db[k](sql);
  const T = { a: 'safe', set() { this.a = 'qu' + 'ery'; } };
  T.set();
  return db[T.a](sql);
}
function run(file, args) { return spawnSync(file, args); }
export function shell(line, prog) {
  spawnSync('sh', ['-c', 'eval "$1"', 'sh', line]);
  spawn('bash', ['-c', '. "$1"', 'bash', line]);
  run('sh', ['-c', 'eval "$1"', 'sh', line]);
  run(prog, ['x']);
}
