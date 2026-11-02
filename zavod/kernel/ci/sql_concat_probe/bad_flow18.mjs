// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow18.mjs — проба 3.3.10.2 (аудит M3310-R15B-07): запуск node
//   с постоянным именем из чужой папки (cwd) и со средой, которая загружает код. Файл закреплён верной суммой в
//   bad_pin18.txt, запуск разрешён — находки cwd и среды всё равно остаются.
// ДАТА: 2026-11-02 15:09 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
import { spawn } from 'node:child_process';
export const a = () => spawn('node', ['known.mjs'], { cwd: '/tmp', shell: false });
export const b = () => spawn('node', ['known.mjs'], { env: { NODE_OPTIONS: '--require=/tmp/extra.cjs' } });
