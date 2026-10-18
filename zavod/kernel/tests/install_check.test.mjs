// ДОКУМЕНТ: tests/install_check.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 15:00 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-18 15:00 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: проверки ci/install_check.mjs без установки: вход привратника (настоящий сервер на свободном порту),
//   сравнение прав с §2, закреплённые суммы установщика, суммы квитанции (лишний и изменённый файл — FAIL),
//   на Windows — запуск PowerShell-части чтения прав.

import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { createHash, generateKeyPairSync } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createGateServer } from '../src/gate_server.mjs';
import { expectedAcl, sameAcl, gateChecks, installerPins, receiptChecks, readAclState, DIRS, tryListen } from '../ci/install_check.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const sha = (b) => createHash('sha256').update(b).digest('hex');

async function freePort() {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)); });
  });
}

test('gateChecks: настоящий привратник проходит все проверки, чужой ключ — нет', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-ic-gate-'));
  const stop = join(dir, 'STOP'); writeFileSync(stop, 'RUN');
  const key = generateKeyPairSync('ed25519');
  const other = generateKeyPairSync('ed25519');
  const port = await freePort();
  const gate = createGateServer({ port, privateKey: key.privateKey, stopFile: stop, onCommand: async () => ({ status: 200, body: { ok: true } }) });
  await gate.start();
  try {
    const pem = (k) => k.publicKey.export({ type: 'spki', format: 'pem' });
    const good = await gateChecks({ port, publicKeyPem: pem(key), foreignPublicKeyPem: pem(other) });
    assert.deepEqual(good.filter((c) => !c.pass), []);
    assert.equal(good.length, 7);
    // Ключ из public не тот, что у привратника: подпись обязана не пройти.
    const swapped = await gateChecks({ port, publicKeyPem: pem(other), foreignPublicKeyPem: pem(key) });
    assert.deepEqual(swapped.filter((c) => !c.pass).map((c) => c.name).sort(), ['hello_not_signed_by_foreign_key', 'hello_signed_by_public_key']);
    const busy = await tryListen('127.0.0.1', port);
    assert.equal(busy.ok, false);
  } finally { await gate.close(); }
});

test('sameAcl: точный набор записей §2; лишняя запись, запрет или чужой владелец — расхождение', () => {
  const K = 'S-1-5-21-1-2-3-1001', PG = 'S-1-5-80-1-2-3-4-5';
  const want = expectedAcl({ K, PG });
  const asGot = (w) => ({ owner: w.owner, protected: w.protected, rules: w.rules.map(([sid, rights, inh]) => ({ sid, rights, inh, type: 'Allow' })) });
  for (const d of DIRS) assert.ok(sameAcl(asGot(want[d]), want[d]), d);
  const rules = asGot(want.rules);
  assert.equal(rules.owner, K);
  const extra = asGot(want.admin); extra.rules.push({ sid: 'S-1-5-32-545', rights: 'ReadAndExecute, Synchronize', inh: 'ContainerInherit, ObjectInherit', type: 'Allow' });
  assert.equal(sameAcl(extra, want.admin), false);
  const deny = asGot(want.bin); deny.rules[0].type = 'Deny';
  assert.equal(sameAcl(deny, want.bin), false);
  const owner = asGot(want.bin); owner.owner = K;
  assert.equal(sameAcl(owner, want.bin), false);
  const inherited = asGot(want.data); inherited.protected = false;
  assert.equal(sameAcl(inherited, want.data), false);
  assert.equal(sameAcl(undefined, want.data), false);
  // Корень: у Users нет наследуемой записи — иначе чтение распространилось бы на admin и data (ошибка v0.1 установщика).
  const rootRec = asGot(want['.']); rootRec.rules[2].inh = 'ContainerInherit, ObjectInherit';
  assert.equal(sameAcl(rootRec, want['.']), false);
});

test('installerPins: три закреплённые суммы (node, MinGit, установщик EDB) читаются из установщика', () => {
  const pins = installerPins(readFileSync(join(here, '..', 'install', 'install_zavod_kernel.ps1'), 'utf8'));
  assert.deepEqual(Object.keys(pins).sort(), ['mingit', 'node', 'pgsetup']);
  assert.match(pins.node, /^[0-9a-f]{64}$/);
  assert.match(pins.pgsetup, /^[0-9a-f]{64}$/);
});

function fakeRoot() {
  const root = mkdtempSync(join(tmpdir(), 'zavod-ic-root-'));
  const files = { 'bin/node.exe': 'node', 'app/gate.json': '{}', 'app/install/install_zavod_kernel.ps1':
    `  node    = @{ url = 'u'; sha = '${'a'.repeat(64)}' }\n  mingit  = @{ url = 'u'; sha = '${'b'.repeat(64)}' }\n` +
    `  pgsetup = @{ url = 'u'; sha = '${'c'.repeat(64)}'; signer = 'x' }\n` };
  const sums = {};
  for (const [rel, text] of Object.entries(files)) {
    mkdirSync(join(root, dirname(rel)), { recursive: true });
    writeFileSync(join(root, rel), text);
    sums[rel] = sha(Buffer.from(text));
  }
  const receipt = { status: 'OK', mode_active: false, commit: 'f'.repeat(40), file_sums: sums,
    sources: { node: { sha256: 'a'.repeat(64) }, mingit: { sha256: 'b'.repeat(64) }, pgsetup: { sha256: 'c'.repeat(64) } } };
  return { root, receipt };
}

test('receiptChecks: совпадение проходит; лишний, изменённый файл и чужая сумма источника — FAIL', () => {
  const { root, receipt } = fakeRoot();
  assert.deepEqual(receiptChecks(root, receipt).filter((c) => !c.pass), []);
  writeFileSync(join(root, 'app', 'planted.mjs'), 'x');
  const r1 = receiptChecks(root, receipt).find((c) => c.name === 'file_sums_match');
  assert.equal(r1.pass, false); assert.match(r1.got, /extra=1/);
  const { root: root2, receipt: rec2 } = fakeRoot();
  writeFileSync(join(root2, 'bin', 'node.exe'), 'patched');
  rec2.sources.pgsetup.sha256 = 'e'.repeat(64);
  const bad = receiptChecks(root2, rec2).filter((c) => !c.pass).map((c) => c.name).sort();
  assert.deepEqual(bad, ['file_sums_match', 'source_pgsetup_matches_pin']);
});

test('readAclState: PowerShell-часть выполняется и читает права (только Windows)', { skip: process.platform !== 'win32' }, () => {
  const root = mkdtempSync(join(tmpdir(), 'zavod-ic-acl-'));
  mkdirSync(join(root, 'bin'));
  const rf = join(root, 'receipt.json'); writeFileSync(rf, '{"status":"OK"}');
  const st = readAclState(root, rf);
  assert.equal(st.dirs['.'].actual.readable, true);
  assert.match(st.dirs['.'].actual.owner, /^S-1-/);
  assert.ok(Array.isArray(st.dirs.bin.actual.rules));
  assert.equal(st.dirs.admin.actual.readable, false);
  assert.equal(st.pg_service, null);
});

test('pg_files_check: список из дерева (--make) проходит сверку; подмена, лишний и пропавший файл — отказ', async () => {
  const { makeList, verifyTree } = await import('../install/pg_files_check.mjs');
  const root = mkdtempSync(join(tmpdir(), 'zavod-ic-pg-'));
  for (const [rel, text] of [['bin/postgres.exe', 'p'], ['lib/x.dll', 'x'], ['share/a/b.sql', 'b']]) {
    mkdirSync(join(root, dirname(rel)), { recursive: true }); writeFileSync(join(root, rel), text);
  }
  const list = makeList(root);
  assert.deepEqual(list.split('\n').filter(Boolean).map((l) => l.slice(66)), ['bin/postgres.exe', 'lib/x.dll', 'share/a/b.sql']);
  assert.equal(verifyTree(root, list).ok, true);
  writeFileSync(join(root, 'lib', 'x.dll'), 'patched');
  writeFileSync(join(root, 'share', 'planted.sql'), 'z');
  const r = verifyTree(root, list);
  assert.equal(r.ok, false);
  assert.deepEqual([r.mismatch, r.extra], [['lib/x.dll'], ['share/planted.sql']]);
  const empty = mkdtempSync(join(tmpdir(), 'zavod-ic-pg-empty-'));
  assert.throws(() => makeList(empty), /PG_DIR_MISSING/);
});
