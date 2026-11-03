// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow6.mjs — проба карты 3.3.10.2 (аудит M3310-R6-01, -02, -03): примеры
//   аудитора и соседние пути: изменённый список ключей, встроенный модуль по имени, запуск программ из строки.
// ДАТА: 2026-11-02 02:55 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import { execSync } from 'node:child_process';
import * as cp from 'node:child_process';
import { spawn, spawnSync, execFile } from 'node:child_process';
import { promisify } from 'node:util';
export function mutated(db, sql, mutate) {
  const names = ['safe'];
  names[0] = 'qu' + 'ery';
  for (const k of names) db[k](sql);
  const more = ['safe'];
  more.push('x');
  for (const k of more) db[k](sql);
  const given = ['safe'];
  mutate(given);
  given.map((k) => db[k](sql));
}
export function builtin(db, sql) {
  const vm = process.getBuiltinModule('v' + 'm');
  return vm.runInNewContext('db.x(sql)', { db, sql });
}
export function launch(line, code, script) {
  execSync(line);
  cp.execFile('gh', ['x']);
  const r = promisify(spawn);
  execFile('gh', ['x'], { shell: true });
  spawnSync(process.execPath, ['-' + 'e', code]);
  spawnSync('sudo', ['node -e x']);
  spawn('sh', ['-c', script]);
  spawn(process.execPath, []);
  spawn(process.execPath, ['w.mjs'], { env: { NODE_OPTIONS: '--require ./x.cjs' } });
  spawnSync(line, ['x']);
  spawn('bash', ['-s'], { stdio: 'pipe' });
  return r;
}
export function frozen() {
  Object.freeze = (x) => x;
}
