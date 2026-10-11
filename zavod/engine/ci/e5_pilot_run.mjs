// ДОКУМЕНТ: zavod/engine/ci/e5_pilot_run.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-11 19:18 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: настоящий прогон пилота P1 (этап 5, протокол Z1 v1.10, критерии E5-1…E5-4, E5-6, E5-7) на
//   локальном стенде: Kernel (PostgreSQL 16 + Z-EXT-01) и движок Flowable 8.0.0. Один долгоживущий процесс:
//   сам запускает движок с одноразовой учёткой в памяти (в файлы и вывод она не попадает), создаёт участников
//   и заказчика пилота штатными функциями управления, вносит заявку (текст BRIEF) через Kernel и ведёт её по
//   графу H1.31 §12 через оркестратор v0.6 с объектом pilot. Внешние участники (рабочий-рутина, два аудитора,
//   оператор) отвечают через папку inbox; программа печатает строку NEED_… и ждёт файл. Каждая строка вывода
//   рассчитана на Monitor (будит ГД).
// ВЫЗОВ: PGPORT=5436 node ci/e5_pilot_run.mjs  (из zavod/engine; стенд — stage5_pilot/stand/p1_stand.sh up)
// СРЕДА: P1_RUN_DIR (папка прогона: inbox/, out/), P1_PRODUCT_CLONE (клон продукта), P1_PYTHON (python для бота),
//   P1_TAG (тег выпуска, по умолчанию p1-v0.1.0), P1_WORKER_TIMEOUT_MIN (240).
// ОГРАНИЧЕНИЯ: платных API нет; секреты продукта живут в GitHub Secrets и здесь не читаются; учётка движка —
//   случайная строка этого прогона. Ничего не удаляется: папки проверки (git worktree) и выгрузки остаются.
//   Внешнее действие одно — тег выпуска в закрытом репозитории продукта, только после сверки манифеста SR-13.
//   Продолжение прогона после падения процесса не поддерживается (движок на новом файле H2 каждый прогон).

import { readFileSync, writeFileSync, appendFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { spawn, execFile } from 'node:child_process';
import { createHash, randomBytes, randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { Kernel } from '../../kernel/src/kernel.mjs';
import { CONN, withRole, assignAuditor, runStopFile } from '../../kernel/tests/helpers.mjs';
import { sealManifest, loadReleaseRows, releaseViaEgress, MANIFEST_KIND, RELEASE_SCOPE } from '../../kernel/src/release_manifest.mjs';
import { checkOrderHistory } from '../../kernel/src/order_history.mjs';
import { EngineClient, EngineError } from '../src/engine_client.mjs';
import { Orchestrator, ORCH_VERSION } from '../src/orchestrator.mjs';

const pg = createRequire(new URL('../../kernel/package.json', import.meta.url))('pg');
const RT = 'C:/AI/multiagent-runtime';
const REPO_ROOT = new URL('../../../', import.meta.url);
const PRODUCT = 'bereznyi-aleksandr/zavod-p1-bot';
const PRODUCT_ID = 1412203481;
const OUTBOX_KIND = 'zavod.product.release';
const TAG = process.env.P1_TAG || 'p1-v0.1.0';
const RUN = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
const DIR = process.env.P1_RUN_DIR || `${RT}/state/zavod_20261007/stage5_pilot/runs/${RUN}`;
const INBOX = join(DIR, 'inbox');
const OUT = join(DIR, 'out');
const CLONE = process.env.P1_PRODUCT_CLONE || `${RT}/state/zavod_20261007/stage5_pilot/zavod-p1-bot`;
const PY = process.env.P1_PYTHON || 'C:/Users/o.bereznyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const NODE = process.execPath;
const JAVA = `${RT}/java21/jdk-21.0.12.1+1/bin/java.exe`;
const WAR = `${RT}/flowable8/wars/flowable-rest.war`;
const WAR_SHA256 = '9d49ea5ddd8ecd1220c9f42978f8dfb4576399f5830b92a5b7ae872f2f9947e4';
const EPORT = Number(process.env.P1_ENGINE_PORT || 8092);
const WORKER_TIMEOUT_MS = Number(process.env.P1_WORKER_TIMEOUT_MIN || 240) * 60000;
for (const d of [INBOX, OUT]) mkdirSync(d, { recursive: true });

const LOG = join(OUT, 'e5_pilot_run.log');
const log = (...a) => { const s = a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' '); console.log(s); appendFileSync(LOG, s + '\n'); };
const sha = (b) => createHash('sha256').update(b).digest('hex');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const checks = [];
const check = (id, ok, detail) => { checks.push({ id, ok: !!ok, detail }); log(`${ok ? 'CHECK_PASS' : 'CHECK_FAIL'} ${id}:`, detail); };
const writeEvidence = (name, obj) => { const t = JSON.stringify(obj, null, 1); writeFileSync(join(OUT, name), t); return sha(t); };

function run(cmd, args, { cwd, input, maxBuffer = 256 << 20, encoding = 'utf8', env } = {}) {
  return new Promise((resolve) => {
    const p = execFile(cmd, args, { cwd, maxBuffer, encoding, env, windowsHide: true }, (err, stdout, stderr) =>
      resolve({ code: err ? (err.code ?? 1) : 0, stdout, stderr: String(stderr || '') }));
    if (input !== undefined) { p.stdin.write(input); p.stdin.end(); }
  });
}
const gh = async (args) => { const r = await run('gh', args); return r; };
const git = (args, opts = {}) => run('git', ['-C', CLONE, ...args], opts);

// Ждать файл в inbox. Строка NEED_… печатается один раз; файл читается как данные, не как команды.
async function waitInbox(name, need, validate) {
  const f = join(INBOX, name);
  log(`NEED_${need} file=${f}`);
  for (;;) {
    if (existsSync(f)) {
      let v;
      try { v = JSON.parse(readFileSync(f, 'utf8')); } catch (e) { log(`INBOX_BAD_JSON ${name}: ${e.message}`); await sleep(15000); continue; }
      const why = validate(v);
      if (!why) { log(`INBOX_ACCEPTED ${name} sha256=${sha(readFileSync(f))}`); return v; }
      log(`INBOX_REJECTED ${name}: ${why}`);
      await sleep(15000);
      continue;
    }
    await sleep(5000);
  }
}

// ── 1. Движок: одноразовая учётка в памяти, свой файл H2 на прогон ───────────────────────────────
const ENGINE_USER = `zavod-p1-${randomBytes(4).toString('hex')}`;
const ENGINE_PASS = randomBytes(24).toString('hex');
if (sha(readFileSync(WAR)) !== WAR_SHA256) { log('WAR_SHA256_MISMATCH'); process.exit(21); }
const h2 = `${DIR.replace(/\\/g, '/')}/engine_h2/engine_p1`;
const java = spawn(JAVA, ['-Xmx768m', '-jar', WAR, '--server.address=127.0.0.1', `--server.port=${EPORT}`,
  `--spring.datasource.url=jdbc:h2:file:${h2};AUTO_SERVER=FALSE`, '--spring.datasource.username=sa', '--spring.datasource.password=',
  '--flowable.rest.app.create-demo-definitions=false', '--flowable.async-executor-activate=true'],
{ env: { ...process.env, FLOWABLE_REST_APP_ADMIN_USERID: ENGINE_USER, FLOWABLE_REST_APP_ADMIN_PASSWORD: ENGINE_PASS },
  stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
const elog = join(OUT, 'engine.log');
java.stdout.on('data', (d) => appendFileSync(elog, d));
java.stderr.on('data', (d) => appendFileSync(elog, d));
process.on('exit', () => { try { java.kill(); } catch { /* уже остановлен */ } });
for (const s of ['SIGINT', 'SIGTERM']) process.on(s, () => process.exit(130));
const engine = new EngineClient({ base: `http://127.0.0.1:${EPORT}/flowable-rest`, user: ENGINE_USER, pass: ENGINE_PASS });
let up = false;
for (let i = 0; i < 120 && !up; i++) {
  await sleep(2000);
  try { up = (await engine.deployments()) !== undefined; } catch { up = false; }
}
if (!up) { log('ENGINE_NOT_UP (см. out/engine.log)'); process.exit(22); }
log(`=== E5 pilot P1 run ${RUN} orch ${ORCH_VERSION} engine pid ${java.pid} port ${EPORT} dir ${DIR}`);
const XML = readFileSync(new URL('../bpmn/bem_work.bpmn20.xml', import.meta.url), 'utf8');
const dep = await engine.deployChecked('zavod_bem_work.bpmn20.xml', XML);
check('p1_graph_deployed_after_check', !!dep?.id, `deployment ${dep?.id}`);

// ── 2. Участники и заказчик пилота (штатные функции управления) ─────────────────────────────────
const tag = RUN.slice(2, 13).replace('T', '');
const ids = {
  run: RUN, tenant: randomUUID(),
  operator: `human:p1-operator-${tag}`, operatorUser: randomUUID(),
  worker: `claude:p1-worker-${tag}`,
  audOpenai: `codex:p1-aud-chatgpt-${tag}`, audAnthropic: `claude:p1-aud-routine-${tag}`,
};
await withRole('bem_bootstrap_admin', async (c) => {
  const q = (sql, args) => c.query(sql, args);
  await q('SELECT bem_control.create_actor($1, $2, $3, NULL)', [ids.operator, 'human', ids.operatorUser]);
  for (const [a, prov] of [[ids.worker, 'anthropic'], [ids.audOpenai, 'openai'], [ids.audAnthropic, 'anthropic']]) {
    await q('SELECT bem_control.create_actor($1, $2, NULL, NULL)', [a, prov]);
  }
  await q('SELECT bem_control.create_tenant($1, $2, $3, $4, $5)',
    [ids.tenant, `zavod pilot P1 ${RUN}`, ids.operator, ids.operatorUser, { zavod: 'stage5-pilot-P1' }]);
  for (const a of [ids.worker, ids.audOpenai, ids.audAnthropic, ids.operator]) {
    await q("SELECT bem_control.grant_delegation('bem_kernel_rw', $1, $2)", [a, `zavod pilot P1 ${RUN}`]);
  }
  await q('SELECT bem_control.set_outbox_kind_policy($1, $2, $3, $4, $5)',
    [OUTBOX_KIND, false, 'p1-tag-egress 0.1', 'outbox_id', `E5 pilot P1 ${RUN}: git tag in private product repo`]);
});
writeEvidence('pilot_ids.json', ids);
log('PILOT_ACTORS', ids);

// ── 3. Хуки пилота ─────────────────────────────────────────────────────────────────────────────
const branchOf = (wi) => `zavod/p1-${wi.slice(0, 8)}`;
const sys = new Map();       // head_sha → итог системной проверки (номера прогонов CI)
const verdictIds = new Map(); // work_item_id → id записей вердиктов последнего прохода

async function branchHead(branch) {
  const r = await gh(['api', `repos/${PRODUCT}/branches/${encodeURIComponent(branch)}`, '--jq', '.commit.sha']);
  return r.code === 0 && /^[0-9a-f]{40}$/.test(r.stdout.trim()) ? r.stdout.trim() : null;
}
async function hasDone(head) {
  const r = await gh(['api', `repos/${PRODUCT}/contents/WORKER_DONE.txt?ref=${head}`, '--jq', '.sha']);
  return r.code === 0 && r.stdout.trim().length > 0;
}

async function runWorker({ provider, workKey, attempt_no, request }) {
  const branch = branchOf(workKey);
  const base = (await gh(['api', `repos/${PRODUCT}/branches/main`, '--jq', '.commit.sha'])).stdout.trim();
  const before = await branchHead(branch);
  const reqFile = join(OUT, `worker_request_${workKey.slice(0, 8)}_a${attempt_no}.json`);
  const reqSha = writeEvidence(`worker_request_${workKey.slice(0, 8)}_a${attempt_no}.json`,
    { work_item_id: workKey, provider, attempt_no, repo: PRODUCT, branch, base_sha: base, branch_head_before: before, request });
  log(`WORKER_REQUEST wi=${workKey} attempt=${attempt_no} branch=${branch} base=${base} file=${reqFile} sha256=${reqSha}`);
  const t0 = Date.now();
  const failFile = join(INBOX, `worker_failed_${workKey.slice(0, 8)}_a${attempt_no}.json`);
  while (Date.now() - t0 < WORKER_TIMEOUT_MS) {
    if (existsSync(failFile)) { log(`WORKER_FAILED_REPORTED attempt=${attempt_no}`); return { outcome: 'PROVIDER_ERROR', usage: { model: 'claude-routine' } }; }
    const head = await branchHead(branch);
    if (head && head !== before && await hasDone(head)) {
      log(`WORKER_DONE wi=${workKey} head_sha=${head} after ${Math.round((Date.now() - t0) / 60000)} min`);
      return { outcome: 'OK', head_sha: head, usage: { model: 'claude-routine', measured_by: 'LOCAL_ESTIMATE' } };
    }
    await sleep(60000);
  }
  log(`WORKER_TIMEOUT attempt=${attempt_no}`);
  return { outcome: 'PROVIDER_ERROR', usage: { model: 'claude-routine' } };
}

// Запуск workflow продукта из main на заданном head_sha; номер прогона ищется по имени прогона.
async function productWorkflow(file, head) {
  const title = `${file.replace('.yml', '')} ${head}`;
  const d = await gh(['workflow', 'run', file, '-R', PRODUCT, '--ref', 'main', '-f', `head_sha=${head}`]);
  if (d.code !== 0) return { ok: false, run: null, detail: `dispatch rc=${d.code} ${d.stderr.slice(0, 200)}` };
  for (let i = 0; i < 90; i++) {
    await sleep(20000);
    const l = await gh(['run', 'list', '-R', PRODUCT, '--workflow', file, '--limit', '20', '--json', 'databaseId,displayTitle,status,conclusion']);
    const r = (JSON.parse(l.stdout || '[]')).find((x) => x.displayTitle === title);
    if (r && r.status === 'completed') return { ok: r.conclusion === 'success', run: r.databaseId, detail: r.conclusion };
  }
  return { ok: false, run: null, detail: 'timeout' };
}

const FORBIDDEN = [/^\.github\//, /^\.claude\//, /^CLAUDE\.md$/];
async function systemCheck({ work_item_id, head_sha }) {
  const h8 = head_sha.slice(0, 8);
  await git(['fetch', 'origin', 'main', branchOf(work_item_id)]);
  const wt = join(OUT, `wt_${h8}`);
  if (!existsSync(wt)) await git(['worktree', 'add', '--detach', wt, head_sha]);
  const changed = (await git(['diff', '--name-only', `origin/main...${head_sha}`])).stdout.split('\n').filter(Boolean);
  const forbidden = changed.filter((f) => FORBIDDEN.some((re) => re.test(f)));
  const scanOut = join(OUT, `product_scan_${h8}.json`);
  const scan = await run(NODE, [fileURLToPath(new URL('zavod/catalog/ci/product_scan.mjs', REPO_ROOT)), wt, '--head-sha', head_sha, '--out', scanOut]);
  const accOut = join(OUT, `acceptance_${h8}`);
  const acc = await run(NODE, [fileURLToPath(new URL('zavod/catalog/P1_telegram_bot/acceptance/p1_acceptance.mjs', REPO_ROOT)),
    '--cmd', `"${PY}" -m bot`, '--cwd', wt, '--out', accOut]);
  writeFileSync(join(OUT, `acceptance_${h8}.log`), acc.stdout + acc.stderr);
  const local = forbidden.length === 0 && scan.code === 0 && acc.code === 0;
  log(`SYSTEM_CHECK_LOCAL head=${h8} forbidden=${forbidden.join(',') || '-'} scan_rc=${scan.code} acceptance_rc=${acc.code} ${(acc.stdout.match(/P1_ACCEPTANCE=\S+ \S+/) || [''])[0]}`);
  // Живой прогон с секретами продукта — только после чистой локальной проверки (код рабочего видит токен бота).
  const build = local ? await productWorkflow('p1-ci.yml', head_sha) : { ok: false, run: null, detail: 'skipped: local check failed' };
  const live = local && build.ok ? await productWorkflow('p1-live.yml', head_sha) : { ok: false, run: null, detail: 'skipped' };
  const lock = await git(['show', `${head_sha}:requirements.lock`], { encoding: 'buffer' });
  const r = { result: local && build.ok && live.ok && lock.code === 0 ? 'PASS' : 'FAIL', changed, forbidden,
    scan_rc: scan.code, scan_report_sha256: existsSync(scanOut) ? sha(readFileSync(scanOut)) : null,
    acceptance_rc: acc.code, acceptance_sha256: existsSync(join(accOut, 'p1_acceptance.json')) ? sha(readFileSync(join(accOut, 'p1_acceptance.json'))) : null,
    build_run: build.run, build: build.detail, test_run: live.run, live: live.detail,
    lock_sha256: lock.code === 0 ? sha(lock.stdout) : null };
  sys.set(head_sha, r);
  log(`SYSTEM_CHECK head=${h8} result=${r.result} build_run=${r.build_run} (${r.build}) test_run=${r.test_run} (${r.live})`);
  return r;
}

const artifactOf = async (head) => {
  const a = await git(['archive', '--format=tar', head], { encoding: 'buffer' });
  if (a.code !== 0) throw new EngineError('ARTIFACT_FAILED', a.stderr.slice(0, 200));
  return a.stdout;
};

async function prepareRelease({ orch, work_item_id, subject_id, head_sha, command_id }) {
  const s = sys.get(head_sha);
  if (!s || s.result !== 'PASS') throw new EngineError('WORK_NOT_RUNNABLE', `system check for ${head_sha} is not PASS`);
  const summary = { work_item_id, subject_id, head_sha, tag: TAG, repo: PRODUCT, system_check: s, verdict_ids: verdictIds.get(work_item_id) };
  writeEvidence(`w3_request_${head_sha.slice(0, 8)}.json`, summary);
  const w3 = await waitInbox(`w3_${head_sha.slice(0, 8)}.json`, `OPERATOR_W3 head=${head_sha} tag=${TAG}`, (v) =>
    (['RELEASE', 'HOLD'].includes(v?.choice) && v.head_sha === head_sha && typeof v.operator_quote === 'string' && v.operator_quote.length > 0
      ? null : 'need {choice: RELEASE|HOLD, head_sha, operator_quote}'));
  const dec = await orch.cmd('OperatorDecision', { decision_code: RELEASE_SCOPE,
    decision: { subject_id, head_sha, choice: w3.choice, tag: TAG }, note: w3.operator_quote.slice(0, 500) },
  { caller: ids.operator, role: 'operator' });
  if (w3.choice !== 'RELEASE') throw new EngineError('WORK_NOT_RUNNABLE', 'operator W3: HOLD');
  const artifact = await artifactOf(head_sha);
  const manifest = sealManifest({ repo_id: PRODUCT_ID, repo_full_name: PRODUCT, tenant_id: ids.tenant, work_item_id,
    subject_id, head_sha, lock_sha256: s.lock_sha256, artifact_sha256: sha(artifact), build_run: s.build_run,
    test_run: s.test_run, verdict_ids: verdictIds.get(work_item_id), outbox_command_id: command_id,
    decision_evidence_id: dec.evidence_id });
  const ev = await orch.evidence(MANIFEST_KIND, manifest);
  writeEvidence(`manifest_${head_sha.slice(0, 8)}.json`, { manifest, manifest_evidence_id: ev.evidence_id });
  log(`MANIFEST_SEALED sha256=${manifest.manifest_sha256} evidence=${ev.evidence_id} decision=${dec.evidence_id}`);
  return { outbox_kind: OUTBOX_KIND, outbox_payload: { manifest_evidence_id: ev.evidence_id, manifest_sha256: manifest.manifest_sha256,
    repo_id: PRODUCT_ID, repo_full_name: PRODUCT, artifact_sha256: manifest.artifact_sha256, tag: TAG } };
}

// Egress: сверка манифеста SR-13 по строкам Kernel до внешнего вызова; вызов — тег в репозитории продукта.
const egressLog = [];
async function egress(row) {
  try {
    const rows = await withRole('bem_kernel_rw', (c) => loadReleaseRows(c, row));
    const artifact = await artifactOf(rows.manifest.head_sha);
    const res = await releaseViaEgress({ ...rows, artifact }, async ({ manifest_sha256 }) => {
      const t = await gh(['api', '-X', 'POST', `repos/${PRODUCT}/git/refs`, '-f', `ref=refs/tags/${TAG}`, '-f', `sha=${rows.manifest.head_sha}`, '--jq', '.object.sha']);
      return { ok: t.code === 0 && t.stdout.trim() === rows.manifest.head_sha, manifest_sha256, stderr: t.stderr.slice(0, 200) };
    });
    egressLog.push({ outbox_id: row.outbox_id, ...res });
    log(`EGRESS ${res.ok ? 'SENT' : 'FAILED'} tag=${TAG} outbox=${row.outbox_id} manifest=${res.manifest_sha256}`);
    return { outcome: res.ok ? 'SENT' : 'FAILED', detail: { tag: TAG, manifest_sha256: res.manifest_sha256 } };
  } catch (e) {
    egressLog.push({ outbox_id: row.outbox_id, refused: e.code || 'ERROR', message: String(e.message).slice(0, 200) });
    log(`EGRESS_REFUSED outbox=${row.outbox_id} code=${e.code || 'ERROR'}`);
    return { outcome: 'FAILED', detail: { refused: e.code || 'ERROR' } };
  }
}

// ── 4. Заказ ───────────────────────────────────────────────────────────────────────────────────
const kernel = new Kernel({ connection: CONN, stopFile: runStopFile('zavod-p1-stop-') });
await kernel.assertIdentity();
const orch = new Orchestrator({ kernel, engine, actor: ids.worker, tenantId: ids.tenant, providers: ['anthropic'],
  governance: { assignAuditors: async (t, s) => { for (const a of [ids.audOpenai, ids.audAnthropic]) await assignAuditor(t, s, a); } },
  egress, runWorker, log: (...a) => log('ORCH', ...a), pilot: { systemCheck, prepareRelease } });
const brief = readFileSync(new URL('zavod/catalog/P1_telegram_bot/BRIEF.md', REPO_ROOT), 'utf8');
const rules = readFileSync(new URL('./e5_pilot_worker_rules.md', import.meta.url), 'utf8');
const request = `${brief}\n\n---\n${rules}`;
const W = await orch.startWork({ criticality: 'NORMAL', note: `E5 pilot P1 ${RUN}`, request });
log(`ORDER_STARTED wi=${W.work_item_id} pid=${W.pid} request_sha256=${sha(request)}`);

const at = async (act) => (await engine.executions({ processInstanceId: W.pid, activityId: act })).length > 0;
const atTask = async (k) => (await engine.tasks({ processInstanceId: W.pid, taskDefinitionKey: k })).length > 0;
const ended = async () => (await engine.processInstances({ id: W.pid })).length === 0;
const PROVIDER_OF = { openai: ids.audOpenai, anthropic: ids.audAnthropic };
let pass = 0;
while (!(await ended())) {
  await orch.pump();
  if (await at('n15')) {
    pass += 1;
    const v = await engine.processVars(W.pid);
    writeEvidence(`audit_request_p${pass}.json`, { work_item_id: W.work_item_id, subject_id: v.subjectId, head_sha: v.headSha,
      system_check: sys.get(v.headSha) || null, repo: PRODUCT, branch: branchOf(W.work_item_id) });
    const items = await waitInbox(`verdicts_p${pass}.json`, `VERDICTS pass=${pass} head=${v.headSha} subject=${v.subjectId}`, (x) =>
      (Array.isArray(x) && x.length === 2 && ['openai', 'anthropic'].every((p) => x.filter((i) => i.provider === p).length === 1)
        && x.every((i) => ['ACCEPT', 'REVISE', 'BLOCKED'].includes(i.verdict) && i.head_sha === v.headSha && i.evidence && typeof i.evidence === 'object')
        ? null : 'need [{provider: openai|anthropic, verdict, head_sha, evidence:{...}}] x2'));
    const r = await orch.deliverVerdicts(W.pid, items.map((i) => ({ auditor: PROVIDER_OF[i.provider], verdict: i.verdict, evidence: i.evidence })));
    verdictIds.set(W.work_item_id, r.verdict_ids);
    log(`VERDICTS_RECORDED pass=${pass} result=${r.verdict} ids=${r.verdict_ids.join(',')}`);
    continue;
  }
  if (await atTask('n19')) {
    const d = await waitInbox(`n19_p${pass}.json`, `OPERATOR_N19 pass=${pass}`, (x) =>
      (['CONTINUE', 'CANCEL'].includes(x?.choice) && typeof x.operator_quote === 'string' ? null : 'need {choice: CONTINUE|CANCEL, operator_quote}'));
    await orch.operatorDecision(W.pid, ids.operator, d.choice);
    continue;
  }
  if (orch.refused.length) { log('ORDER_REFUSED', orch.refused); break; }
  await sleep(2000);
}

// ── 5. Доказательства ──────────────────────────────────────────────────────────────────────────
const sa = new pg.Client({ ...CONN, user: 'postgres' });
await sa.connect();
const q = async (sql) => (await sa.query(sql, [W.work_item_id])).rows;
const wi = await q('SELECT id, status, revision, criticality FROM bem_core.work_item WHERE id = $1');
const cl = await q('SELECT * FROM bem_core.command_log WHERE work_item_id = $1 ORDER BY created_at, command_id');
const ob = await q('SELECT * FROM bem_core.outbox WHERE work_item_id = $1');
const usage = await q('SELECT * FROM bem_core.usage_record WHERE work_item_id = $1 ORDER BY attempt_no');
const subj = await q('SELECT * FROM bem_core.subject WHERE work_item_id = $1');
await sa.end();
const exportSha = writeEvidence('e5_pilot_export.json', { run: RUN, ids, work_item: wi, command_log: cl, outbox: ob, usage, subjects: subj,
  transitions: orch.transitions, refused: orch.refused, system_checks: Object.fromEntries(sys), egress: egressLog });
const h = checkOrderHistory(cl, W.work_item_id);
check('e51_no_manual_relay', h.ok, `${h.problems.join('; ') || 'ручного переноса нет'}; sha256 ${h.sha256}`);
check('p1_released', wi[0]?.status === 'RELEASED', `status ${wi[0]?.status}`);
check('p1_egress_once', egressLog.filter((e) => e.ok).length === 1 && ob.length === 1 && ob[0].status === 'SENT',
  `egress ${JSON.stringify(egressLog)}; outbox ${ob.map((r) => r.status).join(',')}`);
const FAIL = checks.some((c) => !c.ok);
writeEvidence('e5_pilot_result.json', { result: FAIL ? 'FAIL' : 'PASS', checks, export_sha256: exportSha });
await kernel.close();
log(`=== E5_PILOT_RESULT=${FAIL ? 'FAIL' : 'PASS'} (${checks.filter((c) => c.ok).length}/${checks.length}) export_sha256=${exportSha}`);
process.exit(FAIL ? 1 : 0);
