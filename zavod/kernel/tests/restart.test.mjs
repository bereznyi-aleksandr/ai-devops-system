// ДОКУМЕНТ: tests/restart.test.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:25 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 23:12 +03:00 (v0.2: стоп-файл RUN — M-E35-05)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E3-3 — Kernel убит посреди перехода; после нового старта состояние
//   согласовано, а повтор той же команды не задваивает переход и строку outbox.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Kernel } from '../src/kernel.mjs';
import { CONN, bootFixture, uuid, withRole, runStopFile } from './helpers.mjs';

const countOutbox = (tenant, wi) => withRole('bem_kernel_rw', async (c) => {
  await c.query("SELECT set_config('app.tenant_id', $1, false)", [tenant]);
  const { rows } = await c.query('SELECT count(*)::int AS n FROM bem_core.outbox WHERE work_item_id = $1', [wi]);
  return rows[0].n;
});

const CHILD = fileURLToPath(new URL('./crash_child.mjs', import.meta.url));
let ids;
let kernel;

before(async () => { ids = await bootFixture(); kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-restart-') }); });
after(async () => { await kernel?.close(); });

// Запускает дочерний Kernel, ждёт маркер и убивает процесс жёстко.
function runAndKill(args, marker) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [CHILD, ...args], { env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    let err = '';
    const timer = setTimeout(() => { child.kill('SIGKILL'); reject(new Error(`no marker; out=${out} err=${err}`)); }, 30000);
    child.stdout.on('data', (d) => {
      out += d;
      if (out.includes(marker)) child.kill('SIGKILL');
    });
    child.stderr.on('data', (d) => { err += d; });
    child.on('exit', (code, signal) => { clearTimeout(timer); resolve({ out, err, code, signal }); });
  });
}

const get = (wi) => kernel.execute({ actor_id: ids.author }, { type: 'GetWorkItem', actor_id: ids.author,
  tenant_id: ids.tenantA, payload: { work_item_id: wi } });
const transition = (wi, rev, status, cmd) => kernel.execute({ actor_id: ids.author }, {
  type: 'Transition', actor_id: ids.author, tenant_id: ids.tenantA, command_id: cmd,
  payload: { work_item_id: wi, expected_revision: rev, new_status: status,
    outbox_kind: 'notify.send', outbox_payload: { crash: 'retry' }, evidence: { crash: 'retry' } } });

async function newItem() {
  const wi = uuid();
  const r = await kernel.execute({ actor_id: ids.author }, { type: 'CreateWorkItem', actor_id: ids.author,
    tenant_id: ids.tenantA, payload: { work_item_id: wi, evidence: { test: 'restart' } } });
  assert.equal(r.ok, true, JSON.stringify(r.error));
  return wi;
}

async function waitRolledBack(wi, rev) {
  // База откатывает транзакцию убитого клиента, когда замечает разрыв соединения.
  for (let i = 0; i < 50; i += 1) {
    const g = await get(wi);
    if (g.ok && g.result.revision === rev) return g;
    await new Promise((r) => setTimeout(r, 200));
  }
  return get(wi);
}

test('E3-3a убит внутри транзакции: переход откатан; повтор той же команды применяется один раз', async () => {
  const wi = await newItem();
  const cmd = uuid();
  const k = await runAndKill(['before-commit', ids.author, ids.tenantA, wi, '1', 'PLANNED', cmd], 'IN_TX');
  assert.match(k.out, /IN_TX/);
  const g = await waitRolledBack(wi, 1);
  assert.equal(g.result.status, 'NEW');
  assert.equal(g.result.revision, 1);

  const r1 = await transition(wi, 1, 'PLANNED', cmd);
  assert.equal(r1.ok, true, JSON.stringify(r1.error));
  assert.equal(r1.result.new_revision, 2);
  const r2 = await transition(wi, 1, 'PLANNED', cmd);
  assert.deepEqual(r2.result, r1.result);
  assert.equal(await countOutbox(ids.tenantA, wi), 1);
  assert.equal((await get(wi)).result.revision, 2);
});

test('E3-3b убит после фиксации до ответа: повтор возвращает тот же результат, без второй строки outbox', async () => {
  const wi = await newItem();
  const cmd = uuid();
  const k = await runAndKill(['after-commit', ids.author, ids.tenantA, wi, '1', 'PLANNED', cmd], 'COMMITTED');
  assert.match(k.out, /COMMITTED true/);
  const g = await get(wi);
  assert.equal(g.result.status, 'PLANNED');
  assert.equal(g.result.revision, 2);

  const retry = await kernel.execute({ actor_id: ids.author }, {
    type: 'Transition', actor_id: ids.author, tenant_id: ids.tenantA, command_id: cmd,
    payload: { work_item_id: wi, expected_revision: 1, new_status: 'PLANNED',
      outbox_kind: 'notify.send', outbox_payload: { crash: 'after-commit' }, evidence: { crash: 'after-commit' } } });
  assert.equal(retry.ok, true, JSON.stringify(retry.error));
  assert.equal(retry.result.new_revision, 2);
  assert.ok(retry.result.outbox_id);
  assert.equal(await countOutbox(ids.tenantA, wi), 1);
  assert.equal((await get(wi)).result.revision, 2);
});
