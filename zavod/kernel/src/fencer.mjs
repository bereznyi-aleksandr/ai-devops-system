// ДОКУМЕНТ: src/fencer.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 17:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 21:15 +03:00 (v0.2: ответ на аудит Z5 —
//   M-Z5-01: ограждается вся единица исполнения (cgroup v2), а не один процесс; способ «один процесс»
//   убран совсем; M-Z5-02: запись идёт под входом с полномочием OPERATOR, канон §16 «Оператор»)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: надзиратель попыток отправки (аудит Z4 M-Z4-01, Z5 M-Z5-01/02).
//   (1) Каждая попытка внешней отправки идёт в своём экземпляре среды исполнения и в своей единице
//       исполнения — отдельной cgroup v2 (группа процессов ядра Linux, куда попадают и все потомки,
//       даже отделившиеся через setsid). Надзиратель создаёт единицу, помещает в неё процесс ДО
//       запуска кода исполнителя и выдаёт ему ZAVOD_RUNTIME_INSTANCE.
//   (2) Ограждение: запись 1 в cgroup.kill (ядро завершает ВСЕ процессы единицы), ожидание
//       `populated 0` в cgroup.events, и только после этого record_outbox_fence ролью оператора.
//       Доказательство — наблюдение надзирателя: единица пуста, выход ведущего процесса увиден.
//   (3) В единице остался хоть один процесс, или экземпляр неизвестен — отказ FENCE_RUNTIME_ALIVE /
//       FENCE_RUNTIME_UNKNOWN, база не трогается, строка остаётся UNKNOWN_OUTCOME.
//   (4) Нет cgroup v2 (Windows, ZAVOD_CGROUP_ROOT не задан) — FENCE_UNIT_UNSUPPORTED: попытка
//       неидемпотентной отправки не запускается. Job Object (Windows) и контейнер — этап 4 (E4-2).
// ОГРАНИЧЕНИЯ: Linux, cgroup v2 с cgroup.kill (ядро 5.14+), `sudo -n` без пароля для создания единицы
//   и записи cgroup.kill; код исполнителя после этого работает с uid/gid надзирателя
//   (setpriv --no-new-privs). Пустые каталоги единиц не убираются (правило «ничего не удалять»).
//   Стратегия 'leader-only' — только для теста-мутации E4-8: она нарочно завершает лишь ведущий
//   процесс, и проверка обязана отказать.

import pg from 'pg';
import { spawn, spawnSync } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { hostname } from 'node:os';
import { join } from 'node:path';

export const FENCER_VERSION = '0.2.0';
// Переменные, которые передаются исполнителю. Пароли сюда не входят никогда.
const PASS_ENV = ['PATH', 'HOME', 'LANG', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'CI'];

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

// Единица исполнения — cgroup v2.
export class CgroupUnit {
  static supported(root = process.env.ZAVOD_CGROUP_ROOT) {
    if (process.platform !== 'linux' || !root) return false;
    try { readFileSync(join(root, 'cgroup.procs'), 'utf8'); return true; } catch { return false; }
  }

  constructor(root, runtimeInstance) {
    this.kind = 'CGROUP_V2';
    this.path = join(root, runtimeInstance.replace(/[^A-Za-z0-9_-]/g, '_'));
  }

  // Процесс входит в единицу до exec кода исполнителя; потомки наследуют её всегда.
  spawn(argv, env) {
    const uid = process.getuid();
    const gid = process.getgid();
    const script = 'L=$1; shift; mkdir "$L" && echo $$ > "$L/cgroup.procs" && '
      + `exec setpriv --reuid=${uid} --regid=${gid} --clear-groups --no-new-privs -- "$@"`;
    const pairs = Object.entries(env).map(([k, v]) => `${k}=${v}`);
    return spawn('sudo', ['-n', 'sh', '-c', script, 'sh', this.path, 'env', '-i', ...pairs, ...argv],
      { stdio: ['ignore', 'pipe', 'pipe'] });
  }

  populated() {
    const m = /^populated (\d)$/m.exec(readFileSync(join(this.path, 'cgroup.events'), 'utf8'));
    if (!m) throw new FencerError('FENCE_UNIT_UNREADABLE', this.path);
    return m[1] === '1';
  }

  pids() {
    return readFileSync(join(this.path, 'cgroup.procs'), 'utf8').split('\n').filter(Boolean).map(Number);
  }

  async kill(timeoutMs) {
    const r = spawnSync('sudo', ['-n', 'sh', '-c', 'echo 1 > "$1/cgroup.kill"', 'sh', this.path], { encoding: 'utf8' });
    if (r.status !== 0) throw new FencerError('FENCE_UNIT_KILL_FAILED', (r.stderr || '').trim());
    const until = Date.now() + timeoutMs;
    while (this.populated() && Date.now() < until) await timeout(50);
  }
}

export class SendSupervisor {
  constructor({ connection, killTimeoutMs = 10000, observer, cgroupRoot = process.env.ZAVOD_CGROUP_ROOT } = {}) {
    if (!connection?.user) throw new FencerError('FENCER_CONNECTION_REQUIRED', 'operator connection with user');
    this.pool = new pg.Pool({ ...connection, max: 2 });
    this.killTimeoutMs = killTimeoutMs;
    this.observer = observer || `fencer:${hostname()}:${process.pid}`;
    this.cgroupRoot = cgroupRoot;
    this.runtimes = new Map();
  }

  async close() { await this.pool.end(); }

  // Новый экземпляр среды исполнения и новая единица на одну попытку отправки.
  // Исполнитель сообщает о себе строками JSON в stdout ({"ev": ...}).
  spawnAttempt(modulePath, args = [], { env = {} } = {}) {
    if (!CgroupUnit.supported(this.cgroupRoot)) {
      throw new FencerError('FENCE_UNIT_UNSUPPORTED', 'no cgroup v2 unit available; non-idempotent send is not started');
    }
    const runtimeInstance = `runtime:${randomUUID()}`;
    const unit = new CgroupUnit(this.cgroupRoot, runtimeInstance);
    const base = Object.fromEntries(PASS_ENV.filter((k) => process.env[k] !== undefined).map((k) => [k, process.env[k]]));
    const child = unit.spawn([process.execPath, modulePath, ...args],
      { ...base, ...env, ZAVOD_RUNTIME_INSTANCE: runtimeInstance });
    const rec = { runtimeInstance, unit, child, leaderPid: null, exit: null, events: new EventEmitter(), stderr: '' };
    let buf = '';
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (d) => {
      buf += d;
      let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (!line.startsWith('{')) continue;
        try {
          const m = JSON.parse(line);
          if (m.ev === 'READY') rec.leaderPid = m.pid;
          rec.events.emit('message', m);
        } catch { /* не сообщение исполнителя */ }
      }
    });
    child.stderr.setEncoding('utf8');
    child.stderr.on('data', (d) => { rec.stderr = (rec.stderr + d).slice(-4000); });
    rec.exited = new Promise((resolve) => child.once('exit', (code, signal) => {
      rec.exit = { code, signal, at: new Date().toISOString() };
      resolve(rec.exit);
    }));
    this.runtimes.set(runtimeInstance, rec);
    return { runtimeInstance, child, unitId: unit.path };
  }

  waitMessage(runtimeInstance, ev, ms = 20000) {
    const rec = this.runtimes.get(runtimeInstance);
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error(`no ${ev} from runtime; stderr: ${rec.stderr}`)), ms);
      rec.events.on('message', (m) => { if (m?.ev === ev) { clearTimeout(t); resolve(m); } });
      rec.exited.then((x) => { clearTimeout(t); reject(new Error(`runtime exited ${x.code} before ${ev}; stderr: ${rec.stderr}`)); });
    });
  }

  // Наблюдение: вышел ли ведущий процесс и пуста ли единица целиком.
  observe(runtimeInstance) {
    const rec = this.runtimes.get(runtimeInstance);
    if (!rec) return { known: false, alive: null };
    const populated = rec.unit.populated();
    return { known: true, alive: !rec.exit || populated, populated, exit: rec.exit, unitId: rec.unit.path };
  }

  // Ограждение строки. terminate=false — только наблюдение (живая единица — отказ, база не трогается).
  // strategy 'leader-only' — мутация для теста E4-8: завершить один ведущий процесс.
  async fence({ tenantId, outboxId, leaseEpoch, worker, runtimeInstance }, { terminate = true, strategy = 'unit' } = {}) {
    const rec = this.runtimes.get(runtimeInstance);
    if (!rec) throw new FencerError('FENCE_RUNTIME_UNKNOWN', 'runtime instance was not started by this supervisor');
    const pidsBefore = rec.unit.pids();
    let terminatedBy = 'self';
    if (terminate && (rec.unit.populated() || !rec.exit)) {
      terminatedBy = 'fencer';
      if (strategy === 'leader-only') {
        if (rec.leaderPid && pidAlive(rec.leaderPid)) process.kill(rec.leaderPid, 'SIGKILL');
      } else {
        await rec.unit.kill(this.killTimeoutMs);
      }
      await Promise.race([rec.exited, timeout(this.killTimeoutMs)]);
    }
    const seen = this.observe(runtimeInstance);
    if (seen.alive) {
      throw new FencerError('FENCE_RUNTIME_ALIVE',
        `runtime ${runtimeInstance} unit ${rec.unit.path} still has processes ${rec.unit.pids().join(',')}`);
    }
    const evidence = {
      observer: this.observer, fencer_version: FENCER_VERSION,
      exit_observed: true, exit_observed_at: rec.exit.at, runtime_instance: runtimeInstance,
      unit_kind: rec.unit.kind, unit_id: rec.unit.path, unit_empty_observed: true,
      unit_checked_at: new Date().toISOString(), pids_before: pidsBefore, leader_pid: rec.leaderPid,
      exit_code: rec.exit.code, exit_signal: rec.exit.signal, terminated_by: terminatedBy,
    };
    const c = await this.pool.connect();
    let broken = false;
    try {
      await c.query('BEGIN');
      await c.query("SELECT set_config('app.tenant_id', $1, true)", [tenantId]);
      const { rows } = await c.query('SELECT bem_control.record_outbox_fence($1, $2, $3, $4, $5, $6, $7) AS e',
        [tenantId, outboxId, leaseEpoch, worker, runtimeInstance, 'CGROUP_KILLED', evidence]);
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
