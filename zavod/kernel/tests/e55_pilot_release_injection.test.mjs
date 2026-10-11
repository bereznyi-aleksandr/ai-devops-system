// ДОКУМЕНТ: tests/e55_pilot_release_injection.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-11 18:45 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия по задаче E5-5, заготовка)
// НАЗНАЧЕНИЕ: заготовка критерия E5-5 протокола Z1 v1.10 (§8.1: «инъекции 6.2 на конвейере пилота» —
//   работа не потеряна, нет задвоения, нет автоповтора; доказательство: журнал инъекций, SHA-256,
//   head_sha, outbox id). Матрица отказов 6.2 прогоняется на ПУТИ ВЫПУСКА ПИЛОТА P1: строка outbox
//   выпуска продукта (предмет ZAVOD_PRODUCT_RELEASE, ACCEPT {anthropic, openai}, решение оператора,
//   манифест SR-13) → Egress (сверка release_manifest.mjs до отметки) → внешняя заглушка со счётчиками
//   внешних вызовов и внешних эффектов. Точки отказа: I1 Kernel убит до COMMIT; I2 после COMMIT до ответа;
//   I3 Egress упал до отметки; I4 отметка не удалась (аренда истекла); I5 отметка стоит, вызов прошёл,
//   аренда истекла (неидемпотентный вид → UNKNOWN_OUTCOME, второго вызова нет); I6 то же, закреплена
//   «идемпотентно» (повтор тем же ключом, второго эффекта нет); I7n/I7i внешняя система приняла, ответ не
//   дошёл (аренда жива); I8 отметка стоит, исполнитель упал до вызова. Для каждой точки проверены три
//   свойства E5-5: (1) работа не потеряна — ровно одна строка outbox в ожидаемом известном состоянии;
//   (2) нет задвоения — внешних эффектов не больше одного, у неидемпотентного вида и вызов один;
//   (3) нет автоповтора — UNKNOWN_OUTCOME после дополнительных проходов доставщика и попытки захвата
//   не меняет счётчик вызовов и состояние. Журнал инъекций — строки JSON в файле ZAVOD_E55_JOURNAL
//   (CI: артефакт прогона), рядом файл <журнал>.sha256; сумма SHA-256 печатается строкой
//   ZAVOD_E55_JOURNAL_SHA256=...
// ОГРАНИЧЕНИЯ: ЭТО ЗАГОТОВКА НА ЗАГЛУШКЕ, а не закрытие E5-5. Внешняя система — счётчик в памяти, вид
//   строки — zavod.product.release.* с политикой этого прогона, а не боевой адаптер выпуска. E5-5 остаётся
//   OPEN до прогона на реальном конвейере пилота после OD-3 (токен бота) и OD-4 (закрытый репозиторий
//   продукта); этот файл гейты (zavod_stage_gates.json) не меняет и их не закрывает. Единицу исполнения
//   (cgroup/Job Object) и сверку «не отправлено» с ограждением здесь не проверяем: tests/fencer.test.mjs,
//   tests/egress_matrix.test.mjs (E4-8). Стенд PG16 с Z-EXT-01. Механика (claim/отметка/исход) повторяет
//   egress_matrix.test.mjs, но не импортирует его: тестовые файлы запускают свои тесты при загрузке.

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, basename } from 'node:path';
import { Kernel } from '../src/kernel.mjs';
import { CONN, bootFixture, withRole, assignAuditor, runStopFile, uuid } from './helpers.mjs';
import { sealManifest, loadReleaseRows, releaseViaEgress, MANIFEST_KIND, RELEASE_SCOPE } from '../src/release_manifest.mjs';

const CHILD = fileURLToPath(new URL('./e55_crash_child.mjs', import.meta.url));
const sha = (b) => createHash('sha256').update(b).digest('hex');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ARTIFACT = Buffer.from('zavod p1 bot release artifact\n'.repeat(32));
const RT = 'runtime:e55-w1';
const EXPECTED = ['I1', 'I2', 'I3', 'I4', 'I5', 'I6', 'I7n', 'I7i', 'I8'];

let ids;
let kernel;
const journal = [];
const journalPath = process.env.ZAVOD_E55_JOURNAL
  || join(mkdtempSync(join(tmpdir(), 'zavod-e55-')), 'e55_injection_journal.jsonl');

before(async () => {
  ids = await bootFixture();
  kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-e55-') });
  await kernel.assertIdentity();
});
after(async () => {
  await kernel?.close();
  const text = journal.map((e) => JSON.stringify(e)).join('\n') + '\n';
  writeFileSync(journalPath, text);
  const hex = sha(text);
  writeFileSync(`${journalPath}.sha256`, `${hex}  ${basename(journalPath)}\n`);
  const pass = journal.filter((e) => e.verdict === 'PASS').length;
  console.log(`ZAVOD_E55_JOURNAL_SHA256=${hex} file=${journalPath} entries=${journal.length} pass=${pass}`);
});

// Внешняя система-заглушка: calls — внешние вызовы; effects — эффекты по ключу (идемпотентный вид
// сводит повтор с тем же ключом к одному эффекту).
class StubExternal {
  constructor() { this.calls = new Map(); this.effects = new Map(); }
  send(id, key, idempotent) {
    this.calls.set(id, (this.calls.get(id) || 0) + 1);
    if (!(idempotent && this.effects.has(key))) this.effects.set(key, (this.effects.get(key) || 0) + 1);
  }
  n(id) { return this.calls.get(id) || 0; }
  e(key) { return this.effects.get(key) || 0; }
}
const ext = new StubExternal();

// --- Цепочка выпуска пилота (как release_egress.test.mjs: предмет → пара ACCEPT → выпуск → решение
// оператора → Evidence манифеста). Переход со строкой outbox делает вызывающий (в т.ч. убиваемый потомок).
const ROLE_OF = { RecordVerdict: 'auditor', OperatorDecision: 'operator' };
async function ex(actor, type, payload, { command_id } = {}) {
  const r = await kernel.execute({ actor_id: actor, role: ROLE_OF[type] || 'kernel' }, { type, actor_id: actor,
    tenant_id: ids.tenantA, payload, ...(command_id ? { command_id } : {}) });
  assert.equal(r.ok, true, `${type}: ${JSON.stringify(r.error)}`);
  return r.result;
}

async function prepareRelease(kind) {
  const wi = uuid();
  await ex(ids.author, 'CreateWorkItem', { work_item_id: wi, evidence: { test: 'E5-5' } });
  const subj = uuid();
  const head = sha(subj).slice(0, 40);
  await ex(ids.author, 'PublishSubject', { subject_id: subj, work_item_id: wi, head_sha: head, criticality: 'NORMAL',
    scope: RELEASE_SCOPE, authors: [ids.author], evidence: { test: 'E5-5' } });
  for (const a of [ids.audOpenai, ids.audAnthropic]) {
    await assignAuditor(ids.tenantA, subj, a);
    await ex(a, 'RecordVerdict', { subject_id: subj, head_sha: head, verdict: 'ACCEPT', evidence: { reviewed: head } });
  }
  assert.equal((await ex(ids.author, 'ReleaseSubject', { subject_id: subj, head_sha: head })).released, true);
  const decisionId = (await ex(ids.humanA, 'OperatorDecision', { decision_code: RELEASE_SCOPE,
    decision: { subject_id: subj, head_sha: head }, note: 'E5-5 test' })).evidence_id;
  const cmd = uuid();
  const manifest = sealManifest({
    repo_id: 812345678, repo_full_name: 'zavod-products/p1-bot', tenant_id: ids.tenantA, work_item_id: wi,
    subject_id: subj, head_sha: head, lock_sha256: sha('package-lock'), artifact_sha256: sha(ARTIFACT),
    build_run: 37900000001, test_run: 37900000002, verdict_ids: [uuid(), uuid()],
    outbox_command_id: cmd, decision_evidence_id: decisionId,
  });
  const manifestId = (await ex(ids.author, 'RecordEvidence', { kind: MANIFEST_KIND, payload: manifest })).evidence_id;
  const payload = { manifest_evidence_id: manifestId, manifest_sha256: manifest.manifest_sha256, repo_id: 812345678,
    repo_full_name: 'zavod-products/p1-bot', artifact_sha256: manifest.artifact_sha256 };
  return { wi, head, cmd, kind, payload, manifest_sha256: manifest.manifest_sha256 };
}

const transition = (p) => kernel.execute({ actor_id: ids.author, role: 'kernel' }, { type: 'Transition',
  actor_id: ids.author, tenant_id: ids.tenantA, command_id: p.cmd,
  payload: { work_item_id: p.wi, expected_revision: 1, new_status: 'PLANNED', evidence: { test: 'E5-5' },
    outbox_kind: p.kind, outbox_payload: p.payload } });
const getWi = (wi) => kernel.execute({ actor_id: ids.author, role: 'kernel' }, { type: 'GetWorkItem', actor_id: ids.author,
  tenant_id: ids.tenantA, payload: { work_item_id: wi } });
const outboxRows = (wi) => withRole('postgres', async (c) =>
  (await c.query('SELECT id, idempotency_key, status, lease_epoch, send_policy_idempotent, result FROM bem_core.outbox WHERE work_item_id = $1', [wi])).rows);

async function commitRelease(p) {
  const r = await transition(p);
  assert.equal(r.ok, true, JSON.stringify(r.error));
  const rows = await outboxRows(p.wi);
  assert.equal(rows.length, 1);
  return rows[0];
}

// Убить Kernel-потомка на переходе выпуска (как restart.test.mjs, E3-3).
function runAndKill(p, mode, marker) {
  return new Promise((resolve, reject) => {
    const args = [mode, ids.author, ids.tenantA, p.wi, '1', 'PLANNED', p.cmd, p.kind,
      Buffer.from(JSON.stringify(p.payload)).toString('base64')];
    const child = spawn(process.execPath, [CHILD, ...args], { env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = ''; let err = '';
    const timer = setTimeout(() => { child.kill('SIGKILL'); reject(new Error(`no marker; out=${out} err=${err}`)); }, 30000);
    child.stdout.on('data', (d) => { out += d; if (out.includes(marker)) child.kill('SIGKILL'); });
    child.stderr.on('data', (d) => { err += d; });
    child.on('exit', () => { clearTimeout(timer); resolve({ out, err }); });
  });
}
async function waitRolledBack(wi) {
  for (let i = 0; i < 50; i += 1) {
    const g = await getWi(wi);
    if (g.ok && g.result.revision === 1) return g;
    await sleep(200);
  }
  return getWi(wi);
}

// --- Механика Egress (повторяет egress_matrix.test.mjs).
async function claim(worker, lease, mine) {
  return withRole('bem_kernel_rw', async (c) => {
    const { rows } = await c.query('SELECT * FROM bem_control.claim_outbox_batch(500, $1::interval, $2)', [lease, worker]);
    for (const x of rows.filter((x) => x.outbox_id !== mine)) {
      await c.query('SELECT bem_control.finish_outbox_row($1, $2, $3, \'FAILED\', $4)',
        [x.outbox_id, x.lease_epoch, worker, { released_by_test: 'E5-5' }]);
    }
    return rows.find((x) => x.outbox_id === mine);
  });
}
const kq = async (sql, args) => withRole('bem_kernel_rw', async (c) => (await c.query(sql, args)).rows[0]);
const mark = async (id, epoch, w) => (await kq('SELECT bem_control.mark_outbox_send_started($1, $2, $3, $4) AS ok', [id, epoch, w, RT])).ok;
const finish = async (id, epoch, w, s) => (await kq('SELECT bem_control.finish_outbox_row($1, $2, $3, $4, $5) AS ok', [id, epoch, w, s, { test: 'E5-5' }])).ok;
const setPolicy = (kind, idem, note) => withRole('bem_bootstrap_admin', async (c) =>
  (await c.query('SELECT bem_control.set_outbox_kind_policy($1, $2, $3, $4, $5) AS v',
    [kind, idem, 'stub-adapter 1.0', 'outbox_id', `E5-5: ${note}`])).rows[0].v);

class Crash extends Error {}
// Egress выпуска: сверка манифеста (читает Kernel) → отметка начала отправки → внешний вызов → исход.
// stage задаёт точку отказа. Сверка идёт до отметки, отметка — до внешнего вызова.
async function egressAttempt(row, claimRow, worker, { stage = 'ok', idempotent = false } = {}) {
  try {
    if (stage === 'crash_before_mark') return 'CRASHED';
    const rows = await withRole('bem_kernel_rw', (c) => loadReleaseRows(c, claimRow));
    return await releaseViaEgress({ ...rows, artifact: Buffer.from(ARTIFACT) }, async () => {
      if (!(await mark(row.id, claimRow.lease_epoch, worker))) return 'MARK_REFUSED';   // внешнего вызова нет
      if (stage === 'crash_before_call') throw new Crash();
      ext.send(row.id, row.idempotency_key, idempotent);
      if (stage === 'crash_after_call') throw new Crash();                              // исход не записан
      return (await finish(row.id, claimRow.lease_epoch, worker, 'SENT')) ? 'SENT' : 'FINISH_REFUSED';
    });
  } catch (e) {
    if (e instanceof Crash) return 'CRASHED';
    throw e;
  }
}

// Проходы доставщика Kernel: свои строки не должны вызываться снова; чужие строки стенда — SENT-заглушка.
async function kernelRounds(mine, n = 3) {
  for (let i = 0; i < n; i++) {
    await kernel.dispatchOnce(async (r) => {
      if (mine.includes(r.outbox_id)) ext.send(r.outbox_id, 'kernel-round', false);
      return { outcome: 'SENT', detail: { stub: 'E5-5' } };
    }, { limit: 500 });
  }
}

// --- Журнал и три свойства E5-5.
async function injection(id, point, expectation, fn) {
  const entry = { injection: id, point, expectation, verdict: 'FAIL' };
  journal.push(entry);
  try { await fn(entry); entry.verdict = 'PASS'; } catch (e) { entry.error = String(e.message).slice(0, 300); throw e; }
  finally { entry.at = new Date().toISOString(); }
}

// Три свойства E5-5 по строке outbox выпуска; заполняет факт в журнале.
async function checkProperties(entry, p, { status, maxCalls = 1 }) {
  entry.head_sha = p.head;
  entry.work_item_id = p.wi;
  entry.manifest_sha256 = p.manifest_sha256;
  const rows = await outboxRows(p.wi);
  assert.equal(rows.length, 1, 'нет потери и нет второй строки outbox');
  const row = rows[0];
  entry.outbox_id = row.id;
  assert.equal(row.status, status, 'строка в известном ожидаемом состоянии');
  assert.ok(ext.e(row.idempotency_key) <= 1, 'внешних эффектов не больше одного');
  assert.ok(ext.n(row.id) <= maxCalls, `внешних вызовов не больше ${maxCalls}`);
  if (status === 'UNKNOWN_OUTCOME') {
    // нет автоповтора: после дополнительных проходов и попытки захвата — тот же счётчик и состояние
    const calls = ext.n(row.id);
    await kernelRounds([row.id]);
    assert.equal(await claim('w-retry', '30 seconds', row.id), undefined, 'UNKNOWN_OUTCOME не выдаётся на повтор');
    assert.equal(ext.n(row.id), calls, 'автоповтора нет');
    assert.equal((await outboxRows(p.wi))[0].status, 'UNKNOWN_OUTCOME');
  }
  entry.calls = ext.n(row.id);
  entry.effects = ext.e(row.idempotency_key);
  entry.actual = { status, rows: rows.length, calls: entry.calls, effects: entry.effects, lease_epoch: Number(row.lease_epoch) };
}

const kindN = () => `zavod.product.release.e55n.${ids.run}`;
const kindI = () => `zavod.product.release.e55i.${ids.run}`;
let idemReady = false;
async function idemKind() {
  if (!idemReady) { assert.equal(await setPolicy(kindI(), true, 'I6 adapter dedups by key'), 1); idemReady = true; }
  return kindI();
}

test('E5-5 I1: Kernel убит до COMMIT перехода выпуска — откат; повтор той же команды применяется один раз; выпуск один вызов', async () => {
  await injection('I1', 'Kernel убит до COMMIT', 'переход и строка outbox откатаны; повтор применяется один раз; выпуск один вызов', async (entry) => {
    const p = await prepareRelease(kindN());
    const k = await runAndKill(p, 'before-commit', 'IN_TX');
    assert.match(k.out, /IN_TX/);
    const g = await waitRolledBack(p.wi);
    assert.equal(g.result.status, 'NEW');
    assert.equal((await outboxRows(p.wi)).length, 0, 'строка outbox откатана');
    const row = await commitRelease(p);
    const again = await transition(p);
    assert.equal(again.result.outbox_id, row.id, 'повтор возвращает ту же строку');
    const a = await claim('w1', '30 seconds', row.id);
    assert.equal(await egressAttempt(row, a, 'w1'), 'SENT');
    await kernelRounds([row.id]);
    await checkProperties(entry, p, { status: 'SENT' });
    assert.equal(entry.calls, 1);
  });
});

test('E5-5 I2: Kernel убит после COMMIT до ответа — повтор возвращает ту же строку, второй не рождается; выпуск один вызов', async () => {
  await injection('I2', 'после COMMIT, до ответа', 'повтор той же команды возвращает прежний результат; вторая строка outbox не рождается', async (entry) => {
    const p = await prepareRelease(kindN());
    const k = await runAndKill(p, 'after-commit', 'COMMITTED');
    assert.match(k.out, /COMMITTED true/);
    const rows = await outboxRows(p.wi);
    assert.equal(rows.length, 1, 'строка зафиксирована');
    const again = await transition(p);
    assert.equal(again.ok, true, JSON.stringify(again.error));
    assert.equal(again.result.outbox_id, rows[0].id);
    const a = await claim('w1', '30 seconds', rows[0].id);
    assert.equal(await egressAttempt(rows[0], a, 'w1'), 'SENT');
    await kernelRounds([rows[0].id]);
    await checkProperties(entry, p, { status: 'SENT' });
    assert.equal(entry.calls, 1);
  });
});

test('E5-5 I3: Egress упал до отметки — аренда истекла, строка вернулась поколением +1, выпуск один вызов', async () => {
  await injection('I3', 'Egress упал до отметки', 'возврат в очередь с поколением +1; отправка один раз', async (entry) => {
    const p = await prepareRelease(kindN());
    const row = await commitRelease(p);
    const a = await claim('w1', '1 second', row.id);
    assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_before_mark' }), 'CRASHED');
    await sleep(1500);
    const b = await claim('w2', '30 seconds', row.id);
    assert.equal(Number(b.lease_epoch), Number(a.lease_epoch) + 1);
    assert.equal(await egressAttempt(row, b, 'w2'), 'SENT');
    await kernelRounds([row.id]);
    await checkProperties(entry, p, { status: 'SENT' });
    assert.equal(entry.calls, 1);
  });
});

test('E5-5 I4: отметка не удалась (аренда истекла) — false, внешнего вызова нет; следующий исполнитель шлёт один раз', async () => {
  await injection('I4', 'отметка не удалась (аренда истекла)', 'mark = false; внешнего вызова нет; затем один выпуск', async (entry) => {
    const p = await prepareRelease(kindN());
    const row = await commitRelease(p);
    const a = await claim('w1', '1 second', row.id);
    await sleep(1500);
    assert.equal(await egressAttempt(row, a, 'w1'), 'MARK_REFUSED');
    assert.equal(ext.n(row.id), 0, 'внешнего вызова нет');
    const b = await claim('w2', '30 seconds', row.id);
    assert.equal(await egressAttempt(row, b, 'w2'), 'SENT');
    await kernelRounds([row.id]);
    await checkProperties(entry, p, { status: 'SENT' });
    assert.equal(entry.calls, 1);
  });
});

test('E5-5 I5: неидемпотентный выпуск, вызов прошёл, аренда истекла — UNKNOWN_OUTCOME, вызов один, автоповтора нет', async () => {
  await injection('I5', 'отметка + вызов прошёл + аренда истекла (неидемпотентный)', 'UNKNOWN_OUTCOME; второго вызова нет; старый исполнитель исход не пишет; автоповтора нет', async (entry) => {
    const p = await prepareRelease(kindN());
    const row = await commitRelease(p);
    const a = await claim('w1', '1 second', row.id);
    assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_after_call' }), 'CRASHED');
    await sleep(1500);
    assert.equal(await claim('w2', '30 seconds', row.id), undefined, 'второй исполнитель строку не получает');
    const st = (await outboxRows(p.wi))[0];
    assert.equal(st.status, 'UNKNOWN_OUTCOME');
    assert.equal(st.result.reason, 'LEASE_EXPIRED_AFTER_SEND_START');
    assert.equal(await finish(row.id, a.lease_epoch, 'w1', 'SENT'), false, 'старый исполнитель исход не пишет');
    await checkProperties(entry, p, { status: 'UNKNOWN_OUTCOME' });
    assert.equal(entry.calls, 1);
  });
});

test('E5-5 I6: выпуск закреплён «идемпотентно», аренда истекла — повтор тем же ключом, эффект один', async () => {
  await injection('I6', 'отметка + вызов прошёл + аренда истекла (идемпотентно)', 'возврат в очередь; повтор с тем же ключом; эффект один', async (entry) => {
    const p = await prepareRelease(await idemKind());
    const row = await commitRelease(p);
    const a = await claim('w1', '1 second', row.id);
    assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_after_call', idempotent: true }), 'CRASHED');
    assert.equal((await outboxRows(p.wi))[0].send_policy_idempotent, true);
    await sleep(1500);
    const b = await claim('w2', '30 seconds', row.id);
    assert.ok(b, 'идемпотентная строка возвращается в очередь');
    assert.equal(await egressAttempt(row, b, 'w2', { idempotent: true }), 'SENT');
    await kernelRounds([row.id]);
    await checkProperties(entry, p, { status: 'SENT', maxCalls: 2 });
    assert.equal(entry.calls, 2, 'два вызова с одним ключом');
    assert.equal(entry.effects, 1, 'эффект один');
  });
});

for (const idem of [false, true]) {
  test(`E5-5 I7${idem ? 'i' : 'n'} (${idem ? 'идемпотентный' : 'неидемпотентный'}): внешняя система приняла, ответ не дошёл — UNKNOWN_OUTCOME, повтора нет`, async () => {
    await injection(`I7${idem ? 'i' : 'n'}`, `внешняя система приняла, ответ не дошёл (${idem ? 'идемпотентно' : 'неидемпотентно'})`,
      'доставщик Kernel пишет UNKNOWN_OUTCOME; повтора нет', async (entry) => {
        const p = await prepareRelease(idem ? await idemKind() : kindN());
        const row = await commitRelease(p);
        const d = await kernel.dispatchOnce(async (r) => {
          if (r.outbox_id !== row.id) return { outcome: 'SENT', detail: { stub: 'E5-5' } };
          const rows = await withRole('bem_kernel_rw', (c) => loadReleaseRows(c, r));
          await releaseViaEgress({ ...rows, artifact: Buffer.from(ARTIFACT) }, async () => {
            ext.send(row.id, row.idempotency_key, idem);
            throw new Error('reply lost after external accept');
          });
          return { outcome: 'SENT', detail: {} };
        }, { limit: 500 });
        assert.ok(d.results.some((x) => x.outbox_id === row.id && x.outcome === 'UNKNOWN_OUTCOME' && x.finished === true));
        await checkProperties(entry, p, { status: 'UNKNOWN_OUTCOME' });
        assert.equal(entry.calls, 1);
        assert.equal(entry.effects, 1);
      });
  });
}

test('E5-5 I8: отметка стоит, исполнитель упал до вызова — UNKNOWN_OUTCOME, вызовов нет, автоповтора нет', async () => {
  await injection('I8', 'отметка стоит, исполнитель упал до внешнего вызова', 'осторожно UNKNOWN_OUTCOME; вызовов 0; автоповтора нет', async (entry) => {
    const p = await prepareRelease(kindN());
    const row = await commitRelease(p);
    const a = await claim('w1', '1 second', row.id);
    assert.equal(await egressAttempt(row, a, 'w1', { stage: 'crash_before_call' }), 'CRASHED');
    await sleep(1500);
    assert.equal(await claim('w2', '30 seconds', row.id), undefined);
    await checkProperties(entry, p, { status: 'UNKNOWN_OUTCOME', maxCalls: 0 });
    assert.equal(entry.calls, 0);
  });
});

test('E5-5 журнал: все точки отказа записаны, у каждой три свойства проверены, вердикт PASS', async () => {
  assert.deepEqual(journal.map((e) => e.injection).sort(), [...EXPECTED].sort());
  for (const e of journal) {
    assert.equal(e.verdict, 'PASS', e.injection);
    assert.match(e.head_sha, /^[0-9a-f]{40}$/);
    assert.match(e.outbox_id, /^[0-9a-f-]{36}$/);
    assert.ok(Number.isInteger(e.calls) && e.effects <= 1);
  }
});
