// ДОКУМЕНТ: src/fencer.mjs
// ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 17:55 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 22:50 +03:00 (v0.3: единица Windows —
//   Job Object через хозяина win/zavod_jobhost.exe, способ JOB_OBJECT_TERMINATED; закрывает открытый пункт
//   раздела 18 протокола v1.5. v0.2: ответ на аудит Z5 —
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
//   (4) Windows: единица — Job Object (хозяин win/zavod_jobhost.exe: исполнитель запускается
//       приостановленным, входит в Job Object до первой своей команды, выхода из Job Object нет;
//       ограждение — TerminateJobObject и ожидание ActiveProcesses=0). Гибель хозяина или
//       надзирателя гасит единицу целиком (KILL_ON_JOB_CLOSE).
//   (5) Нет ни cgroup v2, ни хозяина Job Object — FENCE_UNIT_UNSUPPORTED: попытка
//       неидемпотентной отправки не запускается. Контейнер — этап 4 (E4-2).
// ОГРАНИЧЕНИЯ: Linux — cgroup v2 с cgroup.kill (ядро 5.14+), `sudo -n` без пароля для создания единицы
//   и записи cgroup.kill; код исполнителя после этого работает с uid/gid надзирателя
//   (setpriv --no-new-privs). Пустые каталоги единиц не убираются (правило «ничего не удалять»).
//   Windows — собранный win/zavod_jobhost.exe (bash win/build_jobhost.sh) или путь в ZAVOD_JOBHOST.
//   Стратегия 'leader-only' — только для теста-мутации E4-8: она нарочно завершает лишь ведущий
//   процесс, и проверка обязана отказать.

import pg from 'pg';
import { spawn, spawnSync } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { readFileSync, existsSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { hostname } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const FENCER_VERSION = '0.3.0';
// Переменные, которые передаются исполнителю. Пароли сюда не входят никогда.
const PASS_ENV = ['PATH', 'HOME', 'LANG', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'CI',
  ...(process.platform === 'win32' ? ['SYSTEMROOT', 'TEMP', 'TMP'] : [])];
export const DEFAULT_JOBHOST = join(dirname(fileURLToPath(import.meta.url)), '..', 'win', 'zavod_jobhost.exe');

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
    this.method = 'CGROUP_KILLED';
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

  async refresh() { /* cgroup читается напрямую */ }
  handle() { /* сообщений хозяина нет */ }

  async kill(timeoutMs) {
    const r = spawnSync('sudo', ['-n', 'sh', '-c', 'echo 1 > "$1/cgroup.kill"', 'sh', this.path], { encoding: 'utf8' });
    if (r.status !== 0) throw new FencerError('FENCE_UNIT_KILL_FAILED', (r.stderr || '').trim());
    const until = Date.now() + timeoutMs;
    while (this.populated() && Date.now() < until) await timeout(50);
  }
}

// Единица исполнения — Job Object Windows. Состояние приходит строками JOB_* от хозяина в том же
// stdout, что и сообщения исполнителя; populated()/pids() — последнее наблюдение, refresh() обновляет.
export class JobObjectUnit {
  static supported(host = process.env.ZAVOD_JOBHOST ?? DEFAULT_JOBHOST) {
    return process.platform === 'win32' && Boolean(host) && existsSync(host);
  }

  constructor(host, runtimeInstance) {
    this.kind = 'JOB_OBJECT';
    this.method = 'JOB_OBJECT_TERMINATED';
    this.host = host;
    this.path = `job:${runtimeInstance}`;
    this.state = { active: null, pids: [] };
    this.gone = false;
    this.waiters = [];
  }

  spawn(argv, env) {
    this.child = spawn(this.host, argv, { env, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
    this.child.once('exit', () => {
      this.gone = true;
      for (const w of this.waiters.splice(0)) w.reject(new FencerError('FENCE_UNIT_UNREADABLE', `${this.path}: host exited`));
    });
    this.path = `${this.path}:host:${this.child.pid}`;
    return this.child;
  }

  handle(m) {
    if (m.ev === 'JOB_STATUS' || m.ev === 'JOB_KILLED') {
      this.state = { active: m.active, pids: m.pids };
      const i = this.waiters.findIndex((w) => w.ev === m.ev);
      if (i >= 0) this.waiters.splice(i, 1)[0].resolve(m);
    }
  }

  ask(cmd, ev, ms) {
    if (this.gone) return Promise.reject(new FencerError('FENCE_UNIT_UNREADABLE', `${this.path}: host exited`));
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new FencerError('FENCE_UNIT_UNREADABLE', `${this.path}: no ${ev}`)), ms);
      this.waiters.push({ ev, resolve: (m) => { clearTimeout(t); resolve(m); }, reject: (e) => { clearTimeout(t); reject(e); } });
      this.child.stdin.write(`${cmd}\n`);
    });
  }

  // Хозяина нет — наблюдать нечем: единица считается непустой (отказ в безопасную сторону).
  populated() { return this.gone || this.state.active === null || this.state.active > 0; }
  pids() { return this.state.pids; }
  async refresh() { await this.ask('STATUS', 'JOB_STATUS', 5000); }

  async kill(timeoutMs) {
    const m = await this.ask(`KILL ${timeoutMs}`, 'JOB_KILLED', timeoutMs + 5000);
    if (m.active > 0) throw new FencerError('FENCE_UNIT_KILL_FAILED', `${this.path}: ${m.active} processes left`);
  }
}

export class SendSupervisor {
  constructor({ connection, killTimeoutMs = 10000, observer, cgroupRoot = process.env.ZAVOD_CGROUP_ROOT,
    jobHost = process.env.ZAVOD_JOBHOST ?? DEFAULT_JOBHOST } = {}) {
    if (!connection?.user) throw new FencerError('FENCER_CONNECTION_REQUIRED', 'operator connection with user');
    this.pool = new pg.Pool({ ...connection, max: 2 });
    this.killTimeoutMs = killTimeoutMs;
    this.observer = observer || `fencer:${hostname()}:${process.pid}`;
    this.cgroupRoot = cgroupRoot;
    this.jobHost = jobHost;
    this.runtimes = new Map();
  }

  // Хозяева Job Object выходят по концу stdin; KILL_ON_JOB_CLOSE гасит то, что осталось в единице.
  async close() {
    for (const r of this.runtimes.values()) r.unit.child?.stdin.end();
    await this.pool.end();
  }

  // Новый экземпляр среды исполнения и новая единица на одну попытку отправки.
  // Исполнитель сообщает о себе строками JSON в stdout ({"ev": ...}).
  spawnAttempt(modulePath, args = [], { env = {} } = {}) {
    const runtimeInstance = `runtime:${randomUUID()}`;
    let unit;
    if (CgroupUnit.supported(this.cgroupRoot)) unit = new CgroupUnit(this.cgroupRoot, runtimeInstance);
    else if (JobObjectUnit.supported(this.jobHost)) unit = new JobObjectUnit(this.jobHost, runtimeInstance);
    else throw new FencerError('FENCE_UNIT_UNSUPPORTED', 'no cgroup v2 or Job Object unit available; non-idempotent send is not started');
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
          if (typeof m.ev === 'string' && m.ev.startsWith('JOB_')) {
            unit.handle(m);
            if (m.ev === 'JOB_LEADER_EXIT') leaderExit(m.code, null);
            continue;
          }
          if (m.ev === 'READY') rec.leaderPid = m.pid;
          rec.events.emit('message', m);
        } catch { /* не сообщение исполнителя */ }
      }
    });
    child.stderr.setEncoding('utf8');
    child.stderr.on('data', (d) => { rec.stderr = (rec.stderr + d).slice(-4000); });
    // Выход ведущего процесса: для cgroup — выход дочернего процесса; для Job Object — сообщение
    // хозяина (ведущий процесс — исполнитель внутри Job Object, хозяин снаружи).
    let resolveExit;
    rec.exited = new Promise((resolve) => { resolveExit = resolve; });
    function leaderExit(code, signal) {
      if (rec.exit) return;
      rec.exit = { code, signal, at: new Date().toISOString() };
      resolveExit(rec.exit);
    }
    child.once('exit', (code, signal) => leaderExit(code, signal));
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
  async observe(runtimeInstance) {
    const rec = this.runtimes.get(runtimeInstance);
    if (!rec) return { known: false, alive: null };
    try { await rec.unit.refresh(); } catch { /* populated() останется «не пуста» */ }
    const populated = rec.unit.populated();
    return { known: true, alive: !rec.exit || populated, populated, exit: rec.exit, unitId: rec.unit.path };
  }

  // Ограждение строки. terminate=false — только наблюдение (живая единица — отказ, база не трогается).
  // strategy 'leader-only' — мутация для теста E4-8: завершить один ведущий процесс.
  async fence({ tenantId, outboxId, leaseEpoch, worker, runtimeInstance }, { terminate = true, strategy = 'unit' } = {}) {
    const rec = this.runtimes.get(runtimeInstance);
    if (!rec) throw new FencerError('FENCE_RUNTIME_UNKNOWN', 'runtime instance was not started by this supervisor');
    await rec.unit.refresh();
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
    const seen = await this.observe(runtimeInstance);
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
        [tenantId, outboxId, leaseEpoch, worker, runtimeInstance, rec.unit.method, evidence]);
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
