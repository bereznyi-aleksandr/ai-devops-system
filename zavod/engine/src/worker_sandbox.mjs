// ДОКУМЕНТ: zavod/engine/src/worker_sandbox.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 07:20 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 08:00 +03:00 (служебные имена Windows)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: запуск рабочего отдельным процессом (этап 4, E4-4 / угроза T1). Рабочий получает только
//   пакет задачи в stdin и окружение из белого списка (без учётки движка, без подключения к базе Kernel,
//   без ключей); у него нет ни Kernel, ни Egress — его вывод только данные: оркестратор не исполняет
//   из вывода ничего, кроме полей outcome и usage. Предел времени — процесс гасится.
// ОГРАНИЧЕНИЯ: сеть и файловую систему рабочего закрывает изоляция OD-2 (облачная сессия, E4-2);
//   этот модуль закрывает окружение, команды и внешние действия. Значения окружения не логируются.

import { spawn } from 'node:child_process';
import { dirname } from 'node:path';
import { findSecret } from '../../kernel/src/guards.mjs';

// Белый список имён окружения рабочего. Всё прочее (в том числе учётка движка и PG*) не передаётся.
export const WORKER_ENV_ALLOW = Object.freeze(['SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG']);
// Windows: библиотека libuv (запуск процессов Node) сама добавляет ребёнку эти служебные имена, даже при
// заданном окружении. Секретов в них нет (пользователь, домашняя папка, системный диск); на Linux их нет.
export const PLATFORM_FORCED_ENV = Object.freeze(process.platform === 'win32' ? ['HOMEDRIVE', 'HOMEPATH', 'LOGONSERVER',
  'PATH', 'SYSTEMDRIVE', 'SYSTEMROOT', 'TEMP', 'USERDOMAIN', 'USERNAME', 'USERPROFILE', 'WINDIR'] : []);
const MAX_OUT = 64 * 1024;

export function workerEnv(parent = process.env) {
  const env = { PATH: dirname(process.execPath), ZAVOD_WORKER: '1' };
  for (const k of WORKER_ENV_ALLOW) if (parent[k] !== undefined) env[k] = parent[k];
  return env;
}

// Возвращает runWorker для оркестратора. onRaw(packet, raw) — для доказательства теста (сырой вывод).
export function childWorker(script, { timeoutMs = 20000, onRaw = () => {} } = {}) {
  return (packet) => new Promise((resolve) => {
    const child = spawn(process.execPath, [script], { env: workerEnv(), stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
    let out = '';
    let err = '';
    const timer = setTimeout(() => child.kill('SIGKILL'), timeoutMs);
    child.stdout.on('data', (d) => { if (out.length < MAX_OUT) out += d; });
    child.stderr.on('data', (d) => { if (err.length < MAX_OUT) err += d; });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      onRaw(packet, { code, signal, stdout: out, stderr: err });
      let r = null;
      try { r = JSON.parse(out.trim().split('\n').at(-1)); } catch { /* не JSON — ошибка рабочего */ }
      // Из вывода берутся только outcome и числа расхода; секретоподобный вывод — ошибка без текста.
      if (code !== 0 || !r || findSecret(out)) {
        resolve({ outcome: 'PROVIDER_ERROR', usage: {}, rejected: findSecret(out) ? 'SECRET_IN_WORKER_OUTPUT' : `exit ${code ?? signal}` });
        return;
      }
      const u = r.usage || {};
      const num = (x) => (Number.isInteger(x) && x >= 0 ? x : 0);
      resolve({ outcome: r.outcome === 'OK' ? 'OK' : 'PROVIDER_ERROR',
        usage: { model: 'zavod-child-worker', input_tokens: num(u.input_tokens), output_tokens: num(u.output_tokens),
          measured_by: 'LOCAL_ESTIMATE' } });
    });
    child.stdin.end(JSON.stringify(packet));
  });
}
