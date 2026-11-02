// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow10.mjs — проба карты 3.3.10.2 (аудит M3310-R9-01): пример
//   аудитора дословно и соседние пути: список запуска дописан push, копией, через другое имя или параметр.
// ДАТА: 2026-11-02 06:11 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import { spawn, spawnSync } from 'node:child_process';
export function run(line) { const argv=['run','--rm','image']; argv.push('sh','-c',line); spawn('docker',argv); }
export function copies(line) {
  const extra = [];
  extra.push('sh', '-c', line);
  spawn('docker', ['run', '--rm', 'image', ...extra]);
  const a = ['run', '--rm', 'image'];
  const b = a;
  b.push('sh', '-c', line);
  spawn('podman', a);
  spawn('git', ['log', ...line.split(' ')]);
}
export function viaParam(args) { return spawnSync('docker', args); }
class Box {
  #docker(args) { return spawnSync('docker', args); }
  open(line) {
    const list = ['exec', 'box'];
    list.push('sh', '-c', line);
    return this.#docker(list);
  }
}
export const box = new Box();
