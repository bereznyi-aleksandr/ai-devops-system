// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow9.mjs — проба карты 3.3.10.2 (аудит M3310-R8-01, -02): примеры
//   аудитора дословно и соседние пути: подмена Object.freeze через другое имя; оболочка и исполнители кода в списках.
// ДАТА: 2026-11-02 04:16 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import { spawn, spawnSync } from 'node:child_process';
export function run(db,sql){const A=Object; A.freeze=x=>x; const names=Object.freeze(['safe']); names[0]='qu'+'ery'; for(const k of names) db[k](sql);}
export function frozen(db, sql, mutate) {
  const names = Object.freeze(['safe']);
  names[0] = 'qu' + 'ery';
  for (const k of names) db[k](sql);
  globalThis.Object.freeze = (x) => x;
  ({ f: Object.freeze } = { f: (x) => x });
  mutate(Array);
}
export function shells(line) {
  spawnSync('sh', ['-c', 'python3 -c "print(1)"']);
  spawn('docker', ['run','--rm','image','sh','-ec','eval "$1"','sh',line]);
  spawn('docker', ['run', '--rm', 'image', 'python3', '-c', line]);
  spawn('docker', ['exec', 'box', 'bash', '-c', 'echo ok']);
}
