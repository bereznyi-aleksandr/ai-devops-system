// ДОКУМЕНТ: src/fencer.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 17:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 17:55 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: надзиратель попыток отправки — ответ на аудит Z4 M-Z4-01 («запись в базе — не ограждение»).
//   (1) Каждая попытка внешней отправки идёт в своём экземпляре среды исполнения: надзиратель сам
//       запускает дочерний процесс и выдаёт ему ZAVOD_RUNTIME_INSTANCE; доставщик Kernel ставит
//       отметку начала отправки с этим экземпляром (mark_outbox_send_started, 4 аргумента).
//   (2) Ограждение: надзиратель сам завершает ИМЕННО этот экземпляр (TerminateProcess / SIGKILL),
//       ждёт его выхода, отдельно проверяет, что процесса с этим номером больше нет, и только после
//       этого пишет record_outbox_fence ролью управления. Доказательство — его собственное наблюдение
//       (observer, exit_observed, exit_observed_at, runtime_instance), не самоотчёт исполнителя.
//   (3) Экземпляр жив после завершения или неизвестен надзирателю — отказ FENCE_RUNTIME_ALIVE /
//       FENCE_RUNTIME_UNKNOWN, в базу ничего не пишется, строка остаётся UNKNOWN_OUTCOME.
// ОГРАНИЧЕНИЯ: подключение — роль управления (bem_governance или её член); Kernel этой роли не имеет.
//   Номер процесса мог быть переиспользован ОС: тогда проверка «жив» даёт ложное «да», и надзиратель
//   отказывает (ошибка в безопасную сторону). Контейнеры (CONTAINER_TERMINATED) — тот же порядок
//   через среду контейнеров, этап 4 (E4-2, изоляция); здесь — процессы.

import pg from 'pg';
import { fork } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { hostname } from 'node:os';

export const FENCER_VERSION = '0.1.0';

export class FencerError extends Error {
  constructor(code, message) {
    super(`${code}: ${message}`);
    this.code = code;
  }
}

// Есть ли процесс с этим номером. EPERM — процесс есть, но чужой: тоже «жив».
export function pidAlive(pid) {
  try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; }
}

const timeout = (ms) => new Promise((r) => setTimeout(r, ms).unref());

export class SendSupervisor {
  constructor({ connection, killTimeoutMs = 10000, observer } = {}) {
    if (!connection?.user) throw new FencerError('FENCER_CONNECTION_REQUIRED', 'governance connection with user');
    this.pool = new pg.Pool({ ...connection, max: 2 });
    this.killTimeoutMs = killTimeoutMs;
    this.observer = observer || `fencer:${hostname()}:${process.pid}`;
    this.runtimes = new Map();
  }

  async close() { await this.pool.end(); }

  // Новый экземпляр среды исполнения на одну попытку отправки.
  spawnAttempt(modulePath, args = [], { env = {} } = {}) {
    const runtimeInstance = `runtime:${randomUUID()}`;
    const child = fork(modulePath, args, {
      env: { ...process.env, ...env, ZAVOD_RUNTIME_INSTANCE: runtimeInstance },
      stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
    });
    const rec = { runtimeInstance, child, pid: child.pid, exit: null };
    rec.exited = new Promise((resolve) => child.once('exit', (code, signal) => {
      rec.exit = { code, signal, at: new Date().toISOString() };
      resolve(rec.exit);
    }));
    this.runtimes.set(runtimeInstance, rec);
    return { runtimeInstance, child, pid: child.pid };
  }

  // Наблюдение: вышел ли экземпляр и нет ли больше его процесса.
  observe(runtimeInstance) {
    const rec = this.runtimes.get(runtimeInstance);
    if (!rec) return { known: false, alive: null };
    return { known: true, alive: !rec.exit || pidAlive(rec.pid), exit: rec.exit, pid: rec.pid };
  }

  // Ограждение строки. terminate=false — только наблюдение без завершения (экземпляр уже вышел сам
  // или проверка «доказательство есть, а среда жива»): живой экземпляр — отказ, база не трогается.
  async fence({ tenantId, outboxId, leaseEpoch, worker, runtimeInstance }, { terminate = true } = {}) {
    const rec = this.runtimes.get(runtimeInstance);
    if (!rec) throw new FencerError('FENCE_RUNTIME_UNKNOWN', 'runtime instance was not started by this supervisor');
    let terminatedBy = 'self';
    if (!rec.exit && terminate) {
      terminatedBy = 'fencer';
      rec.child.kill('SIGKILL');
      await Promise.race([rec.exited, timeout(this.killTimeoutMs)]);
    }
    const seen = this.observe(runtimeInstance);
    if (seen.alive) throw new FencerError('FENCE_RUNTIME_ALIVE', `runtime ${runtimeInstance} pid ${rec.pid} is alive`);
    const evidence = {
      observer: this.observer, fencer_version: FENCER_VERSION,
      exit_observed: true, exit_observed_at: rec.exit.at, runtime_instance: runtimeInstance,
      pid: rec.pid, exit_code: rec.exit.code, exit_signal: rec.exit.signal,
      terminated_by: terminatedBy, pid_absent_checked_at: new Date().toISOString(),
    };
    const c = await this.pool.connect();
    let broken = false;
    try {
      await c.query('BEGIN');
      await c.query("SELECT set_config('app.tenant_id', $1, true)", [tenantId]);
      const { rows } = await c.query('SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7) AS e',
        [tenantId, outboxId, leaseEpoch, worker, runtimeInstance, 'PROCESS_TERMINATED', evidence]);
      await c.query('COMMIT');
      return { evidenceId: rows[0].e, evidence };
    } catch (e) {
      try { await c.query('ROLLBACK'); } catch { broken = true; }
      throw e;
    } finally {
      c.release(broken);
    }
  }
}
