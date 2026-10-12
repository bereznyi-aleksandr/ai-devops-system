// ДОКУМЕНТ: zavod/engine/tests/deploy_egress.test.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 10:14 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 10:39 +03:00 (v0.2: sshInstall заменён
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
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sealManifest, RELEASE_SCOPE } from '../../kernel/src/release_manifest.mjs';
import { deployEgress, ghDeployInstall, localInstall } from '../src/deploy_egress.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const sha = (b) => createHash('sha256').update(b).digest('hex');
const TENANT = randomUUID();
const TARGET = { repo_id: 1412203481, repo_full_name: 'bereznyi-aleksandr/zavod-p1-bot', tenant_id: TENANT };
const ARTIFACT = Buffer.from('product tar bytes '.repeat(64));

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
  const res = await deployEgress(TARGET, f.install).deploy(r);
  assert.deepEqual(res, { state: 'installed', head_sha: r.manifest.head_sha, manifest_sha256: r.manifest.manifest_sha256, outbox_id: r.outbox.id });
  assert.equal(f.jobs.length, 1);
  assert.equal(sha(f.jobs[0].artifact), r.manifest.artifact_sha256);
});

async function refusedBefore(r, code) {
  const f = fake(okReply);
  await assert.rejects(deployEgress(TARGET, f.install).deploy(r), (e) => e.code === code, code);
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
  await assert.rejects(deployEgress(TARGET, async () => 'INSTALL_REFUSED code=ARTIFACT_MISMATCH\n').deploy(r),
    (e) => e.code === 'SERVER_ARTIFACT_MISMATCH');
  await assert.rejects(deployEgress(TARGET, async () => `INSTALL_OK state=installed head=${'b'.repeat(40)}\n`).deploy(rows()),
    (e) => e.code === 'SERVER_NO_CONFIRMATION');
  await assert.rejects(deployEgress(TARGET, async () => '').deploy(rows()), (e) => e.code === 'SERVER_NO_CONFIRMATION');
});

function ghFake({ log, polls = 1 }) {
  const calls = [];
  let views = 0;
  let title = null;
  const exec = async (cmd, args) => {
    calls.push([cmd, args]);
    assert.equal(cmd, 'gh');
    if (args[0] === 'workflow') {
      title = `p1-deploy ${args.find((x) => x.startsWith('request_id=')).slice('request_id='.length)}`;
      return { stdout: '' };
    }
    if (args[0] === 'run' && args[1] === 'list') return { stdout: JSON.stringify([{ databaseId: 9, displayTitle: 'p1-deploy other' }, { databaseId: 77, displayTitle: title }]) };
    if (args.includes('--json')) { views += 1; return { stdout: JSON.stringify({ status: views > polls ? 'completed' : 'in_progress' }) }; }
    return { stdout: log };
  };
  return { calls, exec };
}

test('ghDeployInstall: выкладку делает workflow продукта, ключа у Завода нет', async () => {
  const r = rows();
  const h = r.manifest.head_sha;
  const f = ghFake({ log: `deploy\tpush\t2026-10-12T10:00:00Z ZAVOD_RESULT INSTALL_OK state=installed head=${h}\n`, polls: 2 });
  const res = await deployEgress(TARGET, ghDeployInstall({ repo_full_name: TARGET.repo_full_name, exec: f.exec, wait: async () => {} })).deploy(r);
  assert.equal(res.state, 'installed');
  const run = f.calls[0][1];
  assert.deepEqual(run.slice(0, 5), ['workflow', 'run', 'p1-deploy.yml', '-R', TARGET.repo_full_name]);
  assert.ok(run.includes(`head_sha=${h}`) && run.includes(`request_id=${res.outbox_id}`));
  const b64 = run.find((x) => x.startsWith('manifest_b64=')).slice('manifest_b64='.length);
  assert.deepEqual(JSON.parse(Buffer.from(b64, 'base64').toString('utf8')).manifest, r.manifest);
  assert.ok(f.calls.some(([, a]) => a[0] === 'run' && a[1] === 'view' && a[2] === '77' && a.includes('--log')));
  for (const [, a] of f.calls) assert.ok(!a.some((x) => /ssh|BatchMode|PRIVATE/.test(x)), a.join(' '));
});

test('ghDeployInstall: отказ сервера, пустой журнал, плохой репозиторий', async () => {
  const deny = ghFake({ log: 'x\ty\tZAVOD_RESULT INSTALL_REFUSED code=TENANT_MISMATCH\n' });
  await assert.rejects(deployEgress(TARGET, ghDeployInstall({ repo_full_name: TARGET.repo_full_name, exec: deny.exec, wait: async () => {} })).deploy(rows()),
    (e) => e.code === 'SERVER_TENANT_MISMATCH');
  const quiet = ghFake({ log: 'INSTALL_OK state=installed head=' + 'a'.repeat(40) + '\n' });
  await assert.rejects(deployEgress(TARGET, ghDeployInstall({ repo_full_name: TARGET.repo_full_name, exec: quiet.exec, wait: async () => {} })).deploy(rows()),
    (e) => e.code === 'SERVER_NO_CONFIRMATION');
  assert.throws(() => ghDeployInstall({ repo_full_name: 'x; rm' }), TypeError);
});

test('Linux: сквозной деплой через настоящий install_release.sh', { skip: process.platform === 'win32' }, async () => {
  const d = mkdtempSync(join(tmpdir(), 'zavod-e62-'));
  const root = join(d, 'opt');
  mkdirSync(join(root, 'releases'), { recursive: true });
  writeFileSync(join(d, 'target.env'),
    `REPO_ID="${TARGET.repo_id}"\nREPO_FULL_NAME="${TARGET.repo_full_name}"\nTENANT_ID="${TENANT}"\n`);
  const install = localInstall({ script: join(HERE, '..', '..', 'ops', 'server', 'install_release.sh'),
    env: { ROOT: root, TARGET_ENV: join(d, 'target.env'), JOURNAL: join(d, 'install.jsonl'), RESTART: 'true' } });
  const eg = deployEgress(TARGET, install);
  const { execFileSync } = await import('node:child_process');
  const src = join(d, 'src');
  mkdirSync(join(src, 'bot'), { recursive: true });
  writeFileSync(join(src, 'bot', '__main__.py'), 'print("p1")\n');
  const tar = execFileSync('tar', ['-cf', '-', '-C', src, 'bot']);
  const r = rows({ artifact: tar, head: 'c'.repeat(40) });
  assert.equal((await eg.deploy(r)).state, 'installed');
  assert.equal((await eg.deploy(r)).state, 'already_present');
  assert.equal(realpathSync(join(root, 'current')), realpathSync(join(root, 'releases', 'c'.repeat(40))));
  assert.equal(readFileSync(join(root, 'current', 'bot', '__main__.py'), 'utf8'), 'print("p1")\n');
});
