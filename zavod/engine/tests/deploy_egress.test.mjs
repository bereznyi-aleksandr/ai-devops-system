// ДОКУМЕНТ: zavod/engine/tests/deploy_egress.test.mjs
// ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 10:14 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 11:16 +03:00 (v0.3: аудит ChatGPT
//   S6-prep R2 — билет выпуска: без функции подписи адаптер не создаётся; билет несёт поля манифеста и outbox_id,
//   срок 900 с; sshSigner — настоящая подпись ssh-keygen -Y, проверка -Y verify; ghDeployInstall (L-S6-R2-01):
//   прогон до запуска, прогон не workflow_dispatch, строка из исходника шага и строка чужого outbox — не
//   считаются; два своих прогона — DEPLOY_RUN_AMBIGUOUS; две строки результата — DEPLOY_RUN_NO_RESULT;
//   INSTALL_OK при неуспешном прогоне — DEPLOY_RUN_FAILED; прогон не найден — DEPLOY_RUN_TIMEOUT; на Linux
//   сквозной прогон подписывает билет настоящим ключом, подделка подписи — SERVER_TICKET_BAD_SIGNATURE; v0.2: sshInstall заменён
//   ghDeployInstall — аудит ChatGPT S6-prep M-S6-05/L-S6-01)
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: проверки src/deploy_egress.mjs (E6-2): точный деплой — одна установка; чужой заказчик, чужой
//   репозиторий, подмена байта — отказ до передачи на сервер; отказ сервера и подтверждение чужой версии —
//   отказ адаптера; ghDeployInstall — запуск workflow продукта с манифестом и request_id, поиск своего прогона,
//   разбор только строк ZAVOD_RESULT, ни одного вызова ssh; на Linux — сквозной прогон с
//   настоящим zavod/ops/server/install_release.sh (установка, повтор = already_present, текущая версия).
// ОГРАНИЧЕНИЯ: сети нет; временные папки остаются в tmpdir ОС (ничего не удаляется).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { mkdtempSync, mkdirSync, writeFileSync, realpathSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sealManifest, RELEASE_SCOPE } from '../../kernel/src/release_manifest.mjs';
import { deployEgress, ghDeployInstall, localInstall, sshSigner, TICKET_NAMESPACE } from '../src/deploy_egress.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const sha = (b) => createHash('sha256').update(b).digest('hex');
const TENANT = randomUUID();
const TARGET = { repo_id: 1412203481, repo_full_name: 'bereznyi-aleksandr/zavod-p1-bot', tenant_id: TENANT };
const ARTIFACT = Buffer.from('product tar bytes '.repeat(64));
const SIGN = async (b) => Buffer.from(`sig:${sha(b)}`);
const opts = { sign: SIGN };

function rows({ tenant = TENANT, repo = TARGET, artifact = ARTIFACT, head = 'a'.repeat(40) } = {}) {
  const wi = randomUUID(), subj = randomUUID(), cmd = randomUUID(), dec = randomUUID();
  const r = { repo_id: repo.repo_id, repo_full_name: repo.repo_full_name };
  const manifest = sealManifest({ ...r, tenant_id: tenant, work_item_id: wi, subject_id: subj, head_sha: head,
    lock_sha256: sha('lock'), artifact_sha256: sha(artifact), build_run: 1, test_run: 2,
    verdict_ids: [randomUUID(), randomUUID()], outbox_command_id: cmd, decision_evidence_id: dec });
  return {
    manifest, artifact: Buffer.from(artifact),
    subject: { id: subj, tenant_id: tenant, work_item_id: wi, head_sha: head, scope: RELEASE_SCOPE, released_at: new Date() },
    outbox: { id: randomUUID(), tenant_id: tenant, work_item_id: wi, command_id: cmd, kind: 'zavod.product.release',
      payload: { ...r, manifest_sha256: manifest.manifest_sha256, artifact_sha256: manifest.artifact_sha256 } },
    decision: { id: dec, tenant_id: tenant, kind: 'OPERATOR_DECISION', actor_id: 'human:op', provider: 'human',
      payload: { decision_code: RELEASE_SCOPE, decision: { subject_id: subj, head_sha: head } } },
  };
}

function fake(reply) {
  const jobs = [];
  return { jobs, install: async (job) => { jobs.push(job); return reply(job); } };
}
const okReply = (job) => `INSTALL_OK state=installed head=${job.manifest.head_sha}\n`;

test('точный деплой: одна установка, ответ сервера разобран', async () => {
  const f = fake(okReply);
  const r = rows();
  const res = await deployEgress(TARGET, f.install, opts).deploy(r);
  assert.deepEqual(res, { state: 'installed', head_sha: r.manifest.head_sha, manifest_sha256: r.manifest.manifest_sha256, outbox_id: r.outbox.id, ticket_id: r.outbox.id });
  assert.equal(f.jobs.length, 1);
  assert.equal(sha(f.jobs[0].artifact), r.manifest.artifact_sha256);
  const t = JSON.parse(f.jobs[0].ticket.toString('utf8'));
  assert.equal(t.v, 1);
  assert.equal(t.ticket_id, r.outbox.id);
  assert.equal(t.expires_at - t.issued_at, 900);
  for (const k of ['head_sha', 'artifact_sha256', 'manifest_sha256', 'repo_id', 'repo_full_name', 'tenant_id', 'work_item_id']) assert.equal(t[k], r.manifest[k], k);
  assert.equal(f.jobs[0].ticket_sig.toString(), `sig:${sha(f.jobs[0].ticket)}`);
});

test('без функции подписи билета адаптер не создаётся', () => {
  assert.throws(() => deployEgress(TARGET, async () => ''), TypeError);
  assert.throws(() => deployEgress(TARGET, async () => '', {}), TypeError);
});

async function refusedBefore(r, code) {
  const f = fake(okReply);
  await assert.rejects(deployEgress(TARGET, f.install, opts).deploy(r), (e) => e.code === code, code);
  assert.equal(f.jobs.length, 0, `${code}: передача на сервер до отказа`);
}

test('чужой заказчик — DEPLOY_TENANT_MISMATCH до передачи', () => refusedBefore(rows({ tenant: randomUUID() }), 'DEPLOY_TENANT_MISMATCH'));
test('чужой репозиторий — TARGET_MISMATCH до передачи', () =>
  refusedBefore(rows({ repo: { repo_id: 900000001, repo_full_name: 'other-org/other-bot' } }), 'TARGET_MISMATCH'));
test('подмена байта архива — ARTIFACT_MISMATCH до передачи', () => {
  const r = rows();
  r.artifact[10] ^= 1;
  return refusedBefore(r, 'ARTIFACT_MISMATCH');
});

test('отказ сервера и подтверждение чужой версии — отказ адаптера', async () => {
  const r = rows();
  await assert.rejects(deployEgress(TARGET, async () => 'INSTALL_REFUSED code=ARTIFACT_MISMATCH\n', opts).deploy(r),
    (e) => e.code === 'SERVER_ARTIFACT_MISMATCH');
  await assert.rejects(deployEgress(TARGET, async () => `INSTALL_OK state=installed head=${'b'.repeat(40)}\n`, opts).deploy(rows()),
    (e) => e.code === 'SERVER_NO_CONFIRMATION');
  await assert.rejects(deployEgress(TARGET, async () => '', opts).deploy(rows()), (e) => e.code === 'SERVER_NO_CONFIRMATION');
});

const T0 = Date.parse('2026-10-12T10:00:00Z');
function ghFake({ log, polls = 1, conclusion = 'success', extraRuns = () => [], twins = 0 }) {
  const calls = [];
  let views = 0;
  let title = null;
  let rid = null;
  const exec = async (cmd, args) => {
    calls.push([cmd, args]);
    assert.equal(cmd, 'gh');
    if (args[0] === 'workflow') {
      rid = args.find((x) => x.startsWith('request_id=')).slice('request_id='.length);
      title = `p1-deploy ${rid}`;
      return { stdout: '' };
    }
    if (args[0] === 'run' && args[1] === 'list') {
      const mineRuns = [{ databaseId: 77, displayTitle: title, createdAt: new Date(T0 + 5000).toISOString(), event: 'workflow_dispatch' }];
      for (let i = 0; i < twins; i += 1) mineRuns.push({ databaseId: 78 + i, displayTitle: title, createdAt: new Date(T0 + 6000).toISOString(), event: 'workflow_dispatch' });
      return { stdout: JSON.stringify([{ databaseId: 9, displayTitle: 'p1-deploy other', createdAt: new Date(T0).toISOString(), event: 'workflow_dispatch' },
        ...extraRuns(title), ...mineRuns]) };
    }
    if (args.includes('--json')) {
      views += 1;
      return { stdout: JSON.stringify({ status: views > polls ? 'completed' : 'in_progress', conclusion, event: 'workflow_dispatch', displayTitle: title }) };
    }
    return { stdout: log(rid) };
  };
  return { calls, exec };
}
const gh = (f, more = {}) => ghDeployInstall({ repo_full_name: TARGET.repo_full_name, exec: f.exec, wait: async () => {}, now: () => T0, ...more });
// исходник шага workflow тоже попадает в журнал прогона — эти строки не должны считаться результатом
const DECOY = 'deploy\tpush\t2026-10-12T10:00:01Z echo "ZAVOD_RESULT $REQ $line"\n'
  + 'deploy\tpush\t2026-10-12T10:00:01Z   then echo "ZAVOD_RESULT $REQ INSTALL_REFUSED code=SERVER_NOT_CONFIGURED"; exit 3; fi\n';

test('ghDeployInstall: выкладку делает workflow продукта, ключа у Завода нет', async () => {
  const r = rows();
  const h = r.manifest.head_sha;
  const f = ghFake({ log: (id) => `${DECOY}deploy\tpush\t2026-10-12T10:00:02Z ZAVOD_RESULT ${id} INSTALL_OK state=installed head=${h}\n`, polls: 2,
    extraRuns: (title) => [{ databaseId: 5, displayTitle: title, createdAt: new Date(T0 - 3600000).toISOString(), event: 'workflow_dispatch' },
      { databaseId: 6, displayTitle: title, createdAt: new Date(T0 + 1000).toISOString(), event: 'push' }] });
  const res = await deployEgress(TARGET, gh(f), opts).deploy(r);
  assert.equal(res.state, 'installed');
  const run = f.calls[0][1];
  assert.deepEqual(run.slice(0, 5), ['workflow', 'run', 'p1-deploy.yml', '-R', TARGET.repo_full_name]);
  assert.ok(run.includes(`head_sha=${h}`) && run.includes(`request_id=${res.outbox_id}`));
  const b64 = run.find((x) => x.startsWith('manifest_b64=')).slice('manifest_b64='.length);
  assert.deepEqual(JSON.parse(Buffer.from(b64, 'base64').toString('utf8')).manifest, r.manifest);
  const tk = JSON.parse(Buffer.from(run.find((x) => x.startsWith('ticket_b64=')).slice('ticket_b64='.length), 'base64').toString('utf8'));
  assert.equal(tk.ticket_id, res.outbox_id);
  assert.ok(run.some((x) => x.startsWith('sig_b64=') && x.length > 'sig_b64='.length));
  const list = f.calls.find(([, a]) => a[0] === 'run' && a[1] === 'list')[1];
  assert.ok(list.includes('-e') && list.includes('workflow_dispatch'));
  assert.ok(f.calls.some(([, a]) => a[0] === 'run' && a[1] === 'view' && a[2] === '77' && a.includes('--log')));
  for (const [, a] of f.calls) assert.ok(!a.some((x) => /ssh|BatchMode|PRIVATE/.test(x)), a.join(' '));
});

test('ghDeployInstall: отказ сервера, пустой журнал, плохой репозиторий', async () => {
  const deny = ghFake({ log: (id) => `x\ty\tZAVOD_RESULT ${id} INSTALL_REFUSED code=TENANT_MISMATCH\n`, conclusion: 'failure' });
  await assert.rejects(deployEgress(TARGET, gh(deny), opts).deploy(rows()), (e) => e.code === 'SERVER_TENANT_MISMATCH');
  const quiet = ghFake({ log: () => `${DECOY}INSTALL_OK state=installed head=${'a'.repeat(40)}\n` });
  await assert.rejects(deployEgress(TARGET, gh(quiet), opts).deploy(rows()), (e) => e.code === 'DEPLOY_RUN_NO_RESULT');
  assert.throws(() => ghDeployInstall({ repo_full_name: 'x; rm' }), TypeError);
});

test('ghDeployInstall L-S6-R2-01: два своих прогона, чужой outbox, две строки, успех при сбое, нет прогона', async () => {
  const ok = (id) => `x\ty\tZAVOD_RESULT ${id} INSTALL_OK state=installed head=${'a'.repeat(40)}\n`;
  await assert.rejects(deployEgress(TARGET, gh(ghFake({ log: ok, twins: 1 })), opts).deploy(rows()), (e) => e.code === 'DEPLOY_RUN_AMBIGUOUS');
  const foreign = ghFake({ log: () => `x\ty\tZAVOD_RESULT ${randomUUID()} INSTALL_OK state=installed head=${'a'.repeat(40)}\n` });
  await assert.rejects(deployEgress(TARGET, gh(foreign), opts).deploy(rows()), (e) => e.code === 'DEPLOY_RUN_NO_RESULT');
  const twice = ghFake({ log: (id) => ok(id) + ok(id) });
  await assert.rejects(deployEgress(TARGET, gh(twice), opts).deploy(rows()), (e) => e.code === 'DEPLOY_RUN_NO_RESULT');
  const failed = ghFake({ log: ok, conclusion: 'failure' });
  await assert.rejects(deployEgress(TARGET, gh(failed), opts).deploy(rows()), (e) => e.code === 'DEPLOY_RUN_FAILED');
  const late = ghFake({ log: ok });
  await assert.rejects(deployEgress(TARGET, gh(late, { now: () => T0 + 3600000, maxPolls: 3 }), opts).deploy(rows()),
    (e) => e.code === 'DEPLOY_RUN_TIMEOUT');
  await assert.rejects(gh(late)({ manifest: rows().manifest, outbox_id: randomUUID() }), TypeError);
});

test('sshSigner: настоящая подпись ssh-keygen -Y, проверка -Y verify', async (t) => {
  try { execFileSync('ssh-keygen', ['-V'], { stdio: 'ignore' }); } catch { try { execFileSync('ssh-keygen', ['-?'], { stdio: 'ignore' }); } catch (e) { if (e.code === 'ENOENT') { t.skip('no ssh-keygen'); return; } } }
  const d = mkdtempSync(join(tmpdir(), 'zavod-sign-'));
  const key = join(d, 'k');
  execFileSync('ssh-keygen', ['-q', '-t', 'ed25519', '-N', '', '-C', 'test', '-f', key]);
  const signers = join(d, 'signers');
  writeFileSync(signers, `zavod-release namespaces="${TICKET_NAMESPACE}" ${readFileSync(`${key}.pub`, 'utf8').trim()}\n`);
  const body = Buffer.from('{"v":1}');
  const sig = await sshSigner({ keyPath: key })(body);
  const sp = join(d, 'b.sig');
  writeFileSync(sp, sig);
  execFileSync('ssh-keygen', ['-Y', 'verify', '-f', signers, '-I', 'zavod-release', '-n', TICKET_NAMESPACE, '-s', sp], { input: body });
  assert.throws(() => execFileSync('ssh-keygen', ['-Y', 'verify', '-f', signers, '-I', 'zavod-release', '-n', TICKET_NAMESPACE, '-s', sp],
    { input: Buffer.from('{"v":2}'), stdio: ['pipe', 'ignore', 'ignore'] }));
  assert.throws(() => sshSigner({ keyPath: '' }), TypeError);
});

test('Linux: сквозной деплой через настоящий install_release.sh', { skip: process.platform === 'win32' }, async () => {
  const d = mkdtempSync(join(tmpdir(), 'zavod-e62-'));
  const root = join(d, 'opt');
  mkdirSync(join(root, 'releases'), { recursive: true });
  writeFileSync(join(d, 'target.env'),
    `REPO_ID="${TARGET.repo_id}"\nREPO_FULL_NAME="${TARGET.repo_full_name}"\nTENANT_ID="${TENANT}"\n`);
  const key = join(d, 'release_key');
  execFileSync('ssh-keygen', ['-q', '-t', 'ed25519', '-N', '', '-C', 'test', '-f', key]);
  writeFileSync(join(d, 'release_signers'), `zavod-release namespaces="${TICKET_NAMESPACE}" ${readFileSync(`${key}.pub`, 'utf8').trim()}\n`);
  const install = localInstall({ script: join(HERE, '..', '..', 'ops', 'server', 'install_release.sh'),
    env: { ROOT: root, TARGET_ENV: join(d, 'target.env'), JOURNAL: join(d, 'install.jsonl'), RESTART: 'true',
      RELEASE_SIGNERS: join(d, 'release_signers'), TICKETS: join(d, 'tickets') } });
  const eg = deployEgress(TARGET, install, { sign: sshSigner({ keyPath: key }) });
  const src = join(d, 'src');
  mkdirSync(join(src, 'bot'), { recursive: true });
  writeFileSync(join(src, 'bot', '__main__.py'), 'print("p1")\n');
  const tar = execFileSync('tar', ['-cf', '-', '-C', src, 'bot']);
  const r = rows({ artifact: tar, head: 'c'.repeat(40) });
  assert.equal((await eg.deploy(r)).state, 'installed');
  assert.equal((await eg.deploy(r)).state, 'already_present');
  await assert.rejects(deployEgress(TARGET, install, opts).deploy(rows({ artifact: tar, head: 'd'.repeat(40) })),
    (e) => e.code === 'SERVER_TICKET_BAD_SIGNATURE');
  assert.equal(realpathSync(join(root, 'current')), realpathSync(join(root, 'releases', 'c'.repeat(40))));
  assert.equal(readFileSync(join(root, 'current', 'bot', '__main__.py'), 'utf8'), 'print("p1")\n');
});
