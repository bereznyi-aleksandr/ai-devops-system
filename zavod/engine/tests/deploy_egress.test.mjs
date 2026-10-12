// ДОКУМЕНТ: zavod/engine/tests/deploy_egress.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 10:14 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: проверки src/deploy_egress.mjs (E6-2): точный деплой — одна установка; чужой заказчик, чужой
//   репозиторий, подмена байта — отказ до передачи на сервер; отказ сервера и подтверждение чужой версии —
//   отказ адаптера; sshInstall — только BatchMode и строгая проверка ключа хоста; на Linux — сквозной прогон с
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
import { deployEgress, sshInstall, localInstall } from '../src/deploy_egress.mjs';

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

test('sshInstall: BatchMode, строгая проверка ключа хоста, плохой адрес — отказ', async () => {
  const calls = [];
  const exec = async (cmd, args) => { calls.push([cmd, args]); return { stdout: cmd === 'ssh' ? `INSTALL_OK state=installed head=${'a'.repeat(40)}\n` : '' }; };
  const res = await deployEgress(TARGET, sshInstall({ host: '203.0.113.10', exec })).deploy(rows());
  assert.equal(res.state, 'installed');
  assert.deepEqual(calls.map((c) => c[0]), ['scp', 'ssh']);
  for (const [, args] of calls) {
    assert.ok(args.includes('BatchMode=yes') && args.includes('StrictHostKeyChecking=yes'), args.join(' '));
  }
  assert.ok(calls[1][1].includes('zavod@203.0.113.10'));
  assert.throws(() => sshInstall({ host: 'x; rm' }), TypeError);
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
