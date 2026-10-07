// ДОКУМЕНТ: tests/jobhost.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 23:00 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 23:00 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: единица исполнения Windows без базы данных (идёт в CI на windows-latest).
//   Исполнитель внутри Job Object порождает отделённого (detached) потомка и живёт дальше:
//   (1) потомок внутри единицы; (2) мутация «завершить только ведущий процесс» — потомок жив,
//   единица не пуста; (3) KILL гасит единицу целиком, ActiveProcesses = 0, потомка нет;
//   (4) гибель хозяина гасит всё, что осталось (KILL_ON_JOB_CLOSE).
//   Вне Windows или без собранного win/zavod_jobhost.exe — пропуск; при CI=true на Windows — падение.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JobObjectUnit, DEFAULT_JOBHOST, pidAlive } from '../src/fencer.mjs';

const IN_CI = process.env.CI === 'true';
const WIN = process.platform === 'win32';
const OK = JobObjectUnit.supported();
const skip = !WIN ? 'не Windows' : (OK || IN_CI ? false : 'нет win/zavod_jobhost.exe — только локально');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const LEADER = `const { spawn } = require('node:child_process');
const d = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { detached: true, stdio: 'ignore' });
d.unref();
process.stdout.write(JSON.stringify({ ev: 'DESC', leader: process.pid, pid: d.pid }) + '\\n');
setInterval(() => {}, 1000);`;

function start() {
  const unit = new JobObjectUnit(process.env.ZAVOD_JOBHOST ?? DEFAULT_JOBHOST, `runtime:test-${process.hrtime.bigint()}`);
  const child = unit.spawn([process.execPath, '-e', LEADER], { PATH: process.env.PATH, SYSTEMROOT: process.env.SYSTEMROOT });
  const msgs = [];
  let buf = '';
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', (d) => {
    buf += d;
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const m = JSON.parse(buf.slice(0, i));
      buf = buf.slice(i + 1);
      if (m.ev.startsWith('JOB_')) unit.handle(m);
      msgs.push(m);
    }
  });
  const wait = async (ev) => {
    for (let k = 0; k < 200; k += 1) {
      const m = msgs.find((x) => x.ev === ev);
      if (m) return m;
      await sleep(25);
    }
    throw new Error(`no ${ev}: ${JSON.stringify(msgs)}`);
  };
  return { unit, child, wait };
}

test('Job Object: потомок внутри; «только ведущий» — единица не пуста; KILL — пусто', { skip }, async () => {
  assert.ok(OK, 'CI on Windows must build win/zavod_jobhost.exe');
  const { unit, child, wait } = start();
  const started = await wait('JOB_STARTED');
  const { leader, pid } = await wait('DESC');
  assert.equal(started.pid, leader, 'leader is the process the host started');
  await unit.refresh();
  assert.ok(unit.pids().includes(pid), 'detached descendant is inside the Job Object');
  assert.equal(unit.populated(), true);

  // Мутация: завершить только ведущий процесс — потомок остаётся, единица не пуста.
  process.kill(leader, 'SIGKILL');
  await wait('JOB_LEADER_EXIT');
  await unit.refresh();
  assert.equal(pidAlive(pid), true, 'descendant survived the leader-only kill');
  assert.equal(unit.populated(), true, 'unit is not empty after leader-only kill');

  await unit.kill(5000);
  assert.equal(unit.populated(), false);
  assert.deepEqual(unit.pids(), []);
  await sleep(100);
  assert.equal(pidAlive(pid), false, 'descendant is gone');
  child.stdin.end();
});

test('Job Object: гибель хозяина гасит всю единицу (KILL_ON_JOB_CLOSE)', { skip }, async () => {
  assert.ok(OK, 'CI on Windows must build win/zavod_jobhost.exe');
  const { unit, child, wait } = start();
  const { leader, pid } = await wait('DESC');
  const hostGone = new Promise((r) => child.once('exit', r));
  child.kill('SIGKILL'); // хозяин убит снаружи, команды KILL не было
  await hostGone;
  for (let k = 0; k < 100 && (pidAlive(pid) || pidAlive(leader)); k += 1) await sleep(50);
  assert.equal(pidAlive(leader), false);
  assert.equal(pidAlive(pid), false);
  assert.equal(unit.populated(), true, 'without host the unit is treated as not empty (fail closed)');
});
