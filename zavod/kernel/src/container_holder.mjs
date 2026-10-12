// ДОКУМЕНТ: src/container_holder.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 08:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 08:55 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: PID 1 единицы-контейнера (src/fencer.mjs, ContainerUnit). Запускает исполнителя, передаёт его
//   вывод как есть, сообщает о выходе ведущего процесса строкой {"ev":"JOB_LEADER_EXIT"} и живёт дальше,
//   пока надзиратель не остановит контейнер (docker kill гасит всё пространство процессов).
// ВЫЗОВ: node container_holder.mjs <программа> [аргументы...]   (только внутри контейнера)

import { spawn } from 'node:child_process';

const [cmd, ...args] = process.argv.slice(2);
const leader = spawn(cmd, args, { stdio: ['ignore', 'inherit', 'inherit'] });
leader.on('exit', (code, signal) => process.stdout.write(`${JSON.stringify({ ev: 'JOB_LEADER_EXIT', code, signal })}\n`));
setInterval(() => {}, 1 << 30);
