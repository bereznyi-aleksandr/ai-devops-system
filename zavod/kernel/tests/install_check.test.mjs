// ДОКУМЕНТ: tests/install_check.test.mjs
// ВЕРСИЯ: v0.4  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-18 15:00 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-19 05:59 +03:00 (v0.4: пробная выдача и код-метка, RG30-03; v0.3: в пробном корне есть engine/src/sshsig.mjs; v0.2: проверка npm_lock_list)
// ИСПОЛНИТЕЛЬ: Claude (v0.1–v0.3 сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1; v0.4 сессия 2fc9a1c8-7e6e-4e54-beb1-519c0f3cdba1)
// НАЗНАЧЕНИЕ: проверки ci/install_check.mjs без установки: вход привратника (настоящий сервер на свободном порту),
//   сравнение прав с §2, закреплённые суммы установщика, суммы квитанции (лишний и изменённый файл — FAIL),
//   на Windows — запуск PowerShell-части чтения прав.

import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { createHash, generateKeyPairSync } from 'node:crypto';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createGateServer } from '../src/gate_server.mjs';
import { expectedAcl, sameAcl, gateChecks, installerPins, receiptChecks, readAclState, DIRS, tryListen,
  enrollTrialChecks, leakCanaryChecks } from '../ci/install_check.mjs';

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

// Ответы как у transport.handle для неизвестного кода; leaky — пропуск выдан (обязан не пройти).
function fakeTransport({ leaky = false } = {}) {
  const deny = (status, code) => ({ status, body: { ok: false, error: { code } } });
  return async (body) => {
    if (body.type === 'EnrollSession') {
      if (body.auth !== undefined) return deny(400, 'GATE_BAD_REQUEST');
      if (!/^[0-9a-f]{64}$/.test(body.payload?.claim_code || '')) return deny(403, 'ENROLL_BAD_REQUEST');
      return leaky ? { status: 200, body: { ok: true, result: { pass: 'ab'.repeat(32) } } } : deny(403, 'ENROLL_NOT_FOUND');
    }
    return { status: 403, body: { ok: false, error: { code: 'UNAUTHENTICATED' } } };
  };
}

test('enrollTrialChecks: отказ неизвестному коду и прочим попыткам; выданный пропуск — FAIL', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-ic-enroll-'));
  const stop = join(dir, 'STOP'); writeFileSync(stop, 'RUN');
  for (const leaky of [false, true]) {
    const port = await freePort();
    const gate = createGateServer({ port, privateKey: generateKeyPairSync('ed25519').privateKey, stopFile: stop, onCommand: fakeTransport({ leaky }) });
    await gate.start();
    try {
      const t = await enrollTrialChecks(port);
      assert.match(t.canary, /^[0-9a-f]{64}$/);
      assert.equal(t.rows.length, 4);
      const failed = t.rows.filter((c) => !c.pass).map((c) => c.name);
      assert.deepEqual(failed, leaky ? ['trial_unknown_code_refused_403'] : []);
    } finally { await gate.close(); }
  }
});

test('leakCanaryChecks: код-метка или его SHA-256 в logs/public — FAIL; нет записи отказа — FAIL', () => {
  const canary = 'cd'.repeat(32);
  const make = (logText, pubText = '{}') => {
    const root = mkdtempSync(join(tmpdir(), 'zavod-ic-canary-'));
    mkdirSync(join(root, 'logs')); mkdirSync(join(root, 'public'));
    writeFileSync(join(root, 'logs', 'gate.log'), logText); writeFileSync(join(root, 'public', 'x.json'), pubText);
    return root;
  };
  const refusal = '{"t":"2026-10-19T00:00:00.000Z","ev":"enroll_refused","code":"ENROLL_NOT_FOUND"}\n';
  const names = (rows) => rows.filter((c) => !c.pass).map((c) => c.name);
  assert.deepEqual(names(leakCanaryChecks(make(refusal), canary)), []);
  assert.deepEqual(names(leakCanaryChecks(make(refusal + canary), canary)), ['trial_code_not_in_logs_public']);
  const hashed = sha(Buffer.from(canary, 'hex'));
  assert.deepEqual(names(leakCanaryChecks(make(refusal, hashed), canary)), ['trial_code_not_in_logs_public']);
  assert.deepEqual(names(leakCanaryChecks(make('{}\n'), canary)), ['trial_refusal_logged_without_code']);
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

test('installerPins: четыре закреплённые суммы (node, MinGit, установщик и архив EDB) читаются из установщика', () => {
  const pins = installerPins(readFileSync(join(here, '..', 'install', 'install_zavod_kernel.ps1'), 'utf8'));
  assert.deepEqual(Object.keys(pins).sort(), ['mingit', 'node', 'pgsetup', 'pgzip']);
  for (const k of ['node', 'mingit', 'pgzip']) assert.match(pins[k], /^[0-9a-f]{64}$/);
});

function fakeRoot() {
  const root = mkdtempSync(join(tmpdir(), 'zavod-ic-root-'));
  const files = { 'bin/node.exe': 'node', 'app/gate.json': '{}', 'engine/src/sshsig.mjs': 'export {}', 'app/install/install_zavod_kernel.ps1':
    `  node    = @{ url = 'u'; sha = '${'a'.repeat(64)}' }\n  mingit  = @{ url = 'u'; sha = '${'b'.repeat(64)}' }\n` +
    `  pgsetup = @{ url = 'u'; sha = '${'c'.repeat(64)}'; signer = 'x' }\n  pgzip   = @{ url = 'u'; sha = '${'d'.repeat(64)}' }\n` };
  const sums = {};
  for (const [rel, text] of Object.entries(files)) {
    mkdirSync(join(root, dirname(rel)), { recursive: true });
    writeFileSync(join(root, rel), text);
    sums[rel] = sha(Buffer.from(text));
  }
  const receipt = { status: 'OK', mode_active: false, commit: 'f'.repeat(40), file_sums: sums,
    sources: { node: { sha256: 'a'.repeat(64) }, mingit: { sha256: 'b'.repeat(64) }, pgsetup: { sha256: 'c'.repeat(64) }, pgzip: { sha256: 'd'.repeat(64) } } };
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

test('pg_files_check --copy-listed: копируются ровно файлы списка; подмена у источника — отказ до копирования', async () => {
  const { makeList, copyListed, verifyTree } = await import('../install/pg_files_check.mjs');
  const src = mkdtempSync(join(tmpdir(), 'zavod-ic-cl-'));
  for (const [rel, text] of [['bin/postgres.exe', 'p'], ['lib/x.dll', 'x'], ['share/a/b.sql', 'b']]) {
    mkdirSync(join(src, dirname(rel)), { recursive: true }); writeFileSync(join(src, rel), text);
  }
  const list = makeList(src);
  mkdirSync(join(src, 'share', 'i18n')); writeFileSync(join(src, 'share', 'i18n', 'StackBuilder.mo'), 'extra');
  const dst = join(mkdtempSync(join(tmpdir(), 'zavod-ic-cl-dst-')), 'pgsql');
  const r = copyListed(src, list, dst);
  assert.deepEqual([r.ok, r.copied, r.extra_ignored], [true, 3, 1]);
  assert.equal(verifyTree(dst, list).ok, true);
  assert.equal(copyListed(src, list, dst).stage, 'destination_not_empty');
  writeFileSync(join(src, 'lib', 'x.dll'), 'patched');
  const dst2 = join(mkdtempSync(join(tmpdir(), 'zavod-ic-cl-dst-')), 'pgsql');
  const bad = copyListed(src, list, dst2);
  assert.deepEqual([bad.ok, bad.stage, bad.mismatch], [false, 'source', ['lib/x.dll']]);
  assert.equal(existsSync(dst2), false);
});

test('npm_lock_list: настоящий package-lock.json читается; чужой адрес, не sha512 и выход из node_modules — отказ', async () => {
  const { lockList } = await import('../install/npm_lock_list.mjs');
  const text = readFileSync(join(here, '..', 'package-lock.json'), 'utf8');
  const rows = lockList(text);
  assert.ok(rows.length >= 10);
  assert.ok(rows.every(([n, u, s]) => n.startsWith('node_modules/') && u.startsWith('https://registry.npmjs.org/') && s.length === 88));
  const bad = (patch) => { const l = JSON.parse(text); patch(l.packages); return () => lockList(JSON.stringify(l)); };
  assert.throws(bad((p) => { p['node_modules/pg'].resolved = 'https://evil.example/pg.tgz'; }), /NPM_RESOLVED/);
  assert.throws(bad((p) => { p['node_modules/pg'].integrity = 'sha1-AAAA'; }), /NPM_INTEGRITY/);
  assert.throws(bad((p) => { p['node_modules/../x'] = p['node_modules/pg']; }), /NPM_NAME/);
  assert.throws(bad((p) => { p['node_modules/pg'].link = true; }), /NPM_RESOLVED/);
});
