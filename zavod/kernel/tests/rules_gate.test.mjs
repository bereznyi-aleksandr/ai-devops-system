// ДОКУМЕНТ: tests/rules_gate.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: DRAFT
// ДАТА СОЗДАНИЯ: 2026-10-17 23:51 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-17 23:51 +03:00 (v0.1: пакет Z-RULES-01, проект v1.2 §6)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: проверки src/rules_gate.mjs без базы: настоящий git во временной папке прогона, подставное чтение
//   GitHub, тестовый ключ ssh-ed25519 (подпись собирается так же, как пишет ssh-keygen -Y sign).
//   Включение: слитый PR в main, четыре проверки от назначенного источника на проверенной версии (RG13-04: повторный
//   прогон, повторная отправка с новой версией, чужое приложение), реестр одинаков в head_sha и merge_commit,
//   merge_commit в origin/main, подпись, билет и срок. Проверка перед арендой: чистая копия, HEAD = origin/main.
// ОГРАНИЧЕНИЯ: временные папки создаются в каталоге временных файлов ОС и не удаляются (P4.702); секретов нет.

import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash, generateKeyPairSync, sign as edSign } from 'node:crypto';
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { createRulesGate, parseRegistry, canonicalJson, REGISTRY_PATH, RULES_KEY_PATH, RULES_NAMESPACE,
  REPORT_ACK_NAMESPACE } from '../src/rules_gate.mjs';

const REPO = 'zavod-test/rules';
const APP = 15368;
const TENANT = '11111111-2222-4333-8444-555555555555';
const SUBJECT = '66666666-7777-4888-9999-000000000000';
const PARENTS = { '01_Куратор_ГД': 'OPERATOR', '02_Куратор_производства': '01_Куратор_ГД' };

const ss = (b) => { const n = Buffer.alloc(4); n.writeUInt32BE(Buffer.from(b).length); return Buffer.concat([n, Buffer.from(b)]); };
function newKey() {
  const { publicKey, privateKey } = generateKeyPairSync('ed25519');
  const raw = Buffer.from(publicKey.export({ format: 'jwk' }).x, 'base64url');
  const line = `ssh-ed25519 ${Buffer.concat([ss('ssh-ed25519'), ss(raw)]).toString('base64')} zavod-test`;
  return { privateKey, raw, line };
}
function sshSign(key, message, ns = RULES_NAMESPACE) {
  const pk = Buffer.concat([ss('ssh-ed25519'), ss(key.raw)]);
  const toSign = Buffer.concat([Buffer.from('SSHSIG'), ss(ns), ss(''), ss('sha512'),
    ss(createHash('sha512').update(message).digest())]);
  const sig = Buffer.concat([ss('ssh-ed25519'), ss(edSign(null, toSign, key.privateKey))]);
  const v = Buffer.alloc(4); v.writeUInt32BE(1);
  const blob = Buffer.concat([Buffer.from('SSHSIG'), v, ss(pk), ss(ns), ss(''), ss('sha512'), ss(sig)]);
  return `-----BEGIN SSH SIGNATURE-----\n${blob.toString('base64').match(/.{1,70}/g).join('\n')}\n-----END SSH SIGNATURE-----\n`;
}

// Репозиторий правил: коммит H (проверенная версия) и коммит M поверх него (слияние) с тем же реестром.
function makeRepo({ changeRulesInMerge = false, key = null } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'zavod-rules-gate-'));
  const g = (...args) => execFileSync('git', ['-C', dir, '-c', 'user.name=zavod-test', '-c', 'user.email=zavod-test@example.invalid',
    '-c', 'core.autocrlf=false', ...args], { windowsHide: true }).toString('utf8').trim();
  const put = (p, text) => { mkdirSync(dirname(join(dir, p)), { recursive: true }); writeFileSync(join(dir, p), text); };
  g('init', '-q', '-b', 'main');
  put('AGENTS.md', 'правила v1\n');
  put('roles/01_Куратор_ГД/ROLE.md', 'роль ГД\n');
  put(REGISTRY_PATH, JSON.stringify({ format: 'zavod-rules-registry@v1',
    files: ['AGENTS.md', 'roles/01_Куратор_ГД/ROLE.md'], role_parents: PARENTS }, null, 2));
  if (key) put(RULES_KEY_PATH, `${key.line}\n`);
  put('README.md', 'x\n');
  g('add', '-A');
  g('commit', '-q', '-m', 'rules head');
  const head = g('rev-parse', 'HEAD');
  if (changeRulesInMerge) put('AGENTS.md', 'правила v1 — изменено после аудита\n');
  put('README.md', 'merge\n');
  g('add', '-A');
  g('commit', '-q', '-m', 'merge');
  const merge = g('rev-parse', 'HEAD');
  g('update-ref', 'refs/remotes/origin/main', merge);
  return { dir, g, put, head, merge };
}

function fakeGh({ head, merge, runs, required, pr = {} }) {
  const calls = [];
  const gh = (path) => {
    calls.push(path);
    if (path === `repos/${REPO}/pulls/7`) {
      return { merged: true, base: { ref: 'main' }, merge_commit_sha: merge, head: { sha: head },
        html_url: `https://github.com/${REPO}/pull/7`, ...pr };
    }
    if (path === `repos/${REPO}/branches/main/protection/required_status_checks`) {
      return { checks: required ?? ['static', 'pg16', 'engine-pg', 'engine-pg-probes'].map((c) => ({ context: c, app_id: APP })) };
    }
    if (path === `repos/${REPO}/commits/${head}/check-runs?per_page=100`) return { check_runs: runs };
    throw new Error(`unexpected gh path ${path}`);
  };
  gh.calls = calls;
  return gh;
}
let runId = 1000;
const run = (name, head, extra = {}) => ({ id: runId++, name, head_sha: head, status: 'completed', conclusion: 'success',
  completed_at: '2026-10-17T20:00:00Z', app: { id: APP }, ...extra });
const goodRuns = (head) => ['static', 'pg16', 'engine-pg', 'engine-pg-probes'].map((n) => run(n, head));

function ticketFor(gate, r, over = {}) {
  const digest = gate.readRules(r.merge).digest;
  return JSON.stringify({ tenant_id: TENANT, merge_commit: r.merge, head_sha: r.head, pr_number: 7, registry_digest: digest,
    subject_id: SUBJECT, role_parents: PARENTS, issued_at: '2026-10-17T20:30:00Z', ...over });
}
const NOW = () => Date.parse('2026-10-17T21:00:00Z');

function setup({ runs, required, pr, changeRulesInMerge, signer, bootstrap } = {}) {
  const key = newKey();
  const r = makeRepo({ changeRulesInMerge });
  const gh = fakeGh({ head: r.head, merge: r.merge, runs: runs ? runs(r.head) : goodRuns(r.head), required, pr });
  const gate = createRulesGate({ repoDir: r.dir, repo: REPO, gh, bootstrapKeyLine: (bootstrap ?? key).line, now: NOW, fetch: false });
  const collect = (over = {}, { ns, signKey } = {}) => {
    const text = over.__text ?? ticketFor(gate, r, over);
    return gate.collectActivation({ tenantId: TENANT, prNumber: 7, subjectId: SUBJECT, ticketText: text,
      signature: sshSign(signKey ?? signer ?? key, Buffer.from(text), ns), activeRulesCommit: null });
  };
  return { key, r, gh, gate, collect };
}
const refuses = (fn, code) => assert.throws(fn, (e) => { assert.equal(e.code, code, e.message); return true; });

test('Z-RULES-01: слитый PR, четыре проверки и подпись — факты для базы собраны из GitHub, git и билета', () => {
  const { r, gate, collect } = setup();
  const f = collect();
  assert.equal(f.commit, r.merge);
  assert.equal(f.head_sha, r.head);
  assert.deepEqual(f.role_parents, PARENTS);
  assert.equal(f.registry_digest, gate.readRules(r.merge).digest);
  assert.equal(f.github.pr_url, `https://github.com/${REPO}/pull/7`);
  assert.deepEqual(f.github.check_runs.map((c) => [c.name, c.app_id, c.head_sha, c.conclusion]),
    ['static', 'pg16', 'engine-pg', 'engine-pg-probes'].map((n) => [n, APP, r.head, 'success']));
  assert.ok(f.github.check_runs.every((c) => Number.isInteger(c.check_run_id) && /Z$/.test(c.completed_at)));
  assert.equal(f.signature.namespace, RULES_NAMESPACE);
  assert.match(f.signature.key_fingerprint, /^SHA256:[A-Za-z0-9+/]{43}$/);
  assert.match(f.signature.signed_ticket_sha256, /^[0-9a-f]{64}$/);
});

test('Z-RULES-01: PR не слит или не в main — отказ', () => {
  refuses(() => setup({ pr: { merged: false } }).collect(), 'RULES_PR_NOT_MERGED');
  refuses(() => setup({ pr: { base: { ref: 'dev' } } }).collect(), 'RULES_PR_NOT_MAIN');
});

test('RG13-04: проверка не success, нет прогона, источник не назначен — отказ', () => {
  refuses(() => setup({ runs: (h) => goodRuns(h).map((x) => (x.name === 'pg16' ? { ...x, conclusion: 'failure' } : x)) }).collect(),
    'RULES_CHECK_NOT_PASSED');
  refuses(() => setup({ runs: (h) => goodRuns(h).filter((x) => x.name !== 'engine-pg-probes') }).collect(), 'RULES_CHECK_NOT_PASSED');
  refuses(() => setup({ required: [{ context: 'static', app_id: null }, { context: 'pg16', app_id: APP },
    { context: 'engine-pg', app_id: APP }, { context: 'engine-pg-probes', app_id: APP }] }).collect(), 'RULES_CHECK_SOURCE_UNASSIGNED');
});

test('RG13-04: прогон чужого приложения не считается, даже success', () => {
  refuses(() => setup({ runs: (h) => goodRuns(h).map((x) => (x.name === 'static' ? { ...x, app: { id: 999 } } : x)) }).collect(),
    'RULES_CHECK_NOT_PASSED');
});

test('RG13-04: последний повторный прогон решает — success после failure проходит, failure после success нет', () => {
  const later = (h, first, second) => [...goodRuns(h).filter((x) => x.name !== 'pg16'),
    run('pg16', h, { conclusion: first, completed_at: '2026-10-17T19:00:00Z' }),
    run('pg16', h, { conclusion: second, completed_at: '2026-10-17T19:30:00Z' })];
  assert.equal(setup({ runs: (h) => later(h, 'failure', 'success') }).collect().github.check_runs[1].conclusion, 'success');
  refuses(() => setup({ runs: (h) => later(h, 'success', 'failure') }).collect(), 'RULES_CHECK_NOT_PASSED');
});

test('RG13-04: результат прошлой версии после повторной отправки не принимается', () => {
  const old = 'a'.repeat(40);
  refuses(() => setup({ runs: () => goodRuns(old) }).collect(), 'RULES_CHECK_NOT_PASSED');
});

test('RG12-06: реестр изменён между проверенной версией и слиянием — отказ', () => {
  refuses(() => setup({ changeRulesInMerge: true }).collect(), 'RULES_REGISTRY_CHANGED_AFTER_AUDIT');
});

test('RG12-06: merge_commit не входит в origin/main — отказ', () => {
  const s = setup();
  s.r.g('update-ref', 'refs/remotes/origin/main', s.r.head);
  refuses(() => s.collect(), 'RULES_COMMIT_NOT_IN_MAIN');
});

test('RG12-01: подпись не тем ключом, не того пространства имён, изменённый билет — отказ', () => {
  const s = setup();
  refuses(() => s.collect({}, { signKey: newKey() }), 'RULES_SIGNATURE_INVALID');
  refuses(() => s.collect({}, { ns: REPORT_ACK_NAMESPACE }), 'RULES_SIGNATURE_INVALID');
  const text = ticketFor(s.gate, s.r);
  const sig = sshSign(s.key, Buffer.from(text));
  refuses(() => s.gate.collectActivation({ tenantId: TENANT, prNumber: 7, subjectId: SUBJECT,
    ticketText: text.replace('"pr_number":7', '"pr_number":8'), signature: sig, activeRulesCommit: null }), 'RULES_SIGNATURE_INVALID');
});

test('RG12-01: подписанный билет называет другие факты — отказ по полю', () => {
  const s = setup();
  refuses(() => s.collect({ registry_digest: 'f'.repeat(64) }), 'RULES_SIGNATURE_MISMATCH');
  refuses(() => s.collect({ tenant_id: SUBJECT }), 'RULES_SIGNATURE_MISMATCH');
  refuses(() => s.collect({ head_sha: 'b'.repeat(40) }), 'RULES_SIGNATURE_MISMATCH');
  refuses(() => s.collect({ role_parents: { '01_Куратор_ГД': 'OPERATOR' } }), 'RULES_SIGNATURE_MISMATCH');
});

test('RG12-01: билет старше 24 часов или из будущего — отказ', () => {
  const s = setup();
  refuses(() => s.collect({ issued_at: '2026-10-16T20:59:00Z' }), 'RULES_SIGNATURE_EXPIRED');
  refuses(() => s.collect({ issued_at: '2026-10-17T21:06:00Z' }), 'RULES_SIGNATURE_EXPIRED');
  refuses(() => s.collect({ issued_at: 'вчера' }), 'RULES_SIGNATURE_EXPIRED');
});

test('Z-RULES-01: при действующей версии ключ берётся из её файла, а не ключ установки', () => {
  const opKey = newKey();
  const r = makeRepo({ key: opKey });
  const gh = fakeGh({ head: r.head, merge: r.merge, runs: goodRuns(r.head) });
  const boot = newKey();
  const gate = createRulesGate({ repoDir: r.dir, repo: REPO, gh, bootstrapKeyLine: boot.line, now: NOW, fetch: false });
  const text = ticketFor(gate, r);
  const args = (k) => ({ tenantId: TENANT, prNumber: 7, subjectId: SUBJECT, ticketText: text,
    signature: sshSign(k, Buffer.from(text)), activeRulesCommit: r.head });
  assert.equal(gate.collectActivation(args(opKey)).commit, r.merge);
  refuses(() => gate.collectActivation(args(boot)), 'RULES_SIGNATURE_INVALID');
});

test('RG13-02: подпись оператора под подтверждением отчёта — только билет этого отчёта', () => {
  const s = setup();
  const rep = '12345678-1234-4234-8234-123456789012';
  const sum = 'c'.repeat(64);
  const text = canonicalJson({ tenant_id: TENANT, report_id: rep, report_sha256: sum });
  const ok = s.gate.verifyReportAck({ tenantId: TENANT, reportId: rep, reportSha256: sum, ticketText: text,
    signature: sshSign(s.key, Buffer.from(text), REPORT_ACK_NAMESPACE), activeRulesCommit: null });
  assert.equal(ok.namespace, REPORT_ACK_NAMESPACE);
  refuses(() => s.gate.verifyReportAck({ tenantId: TENANT, reportId: rep, reportSha256: 'd'.repeat(64), ticketText: text,
    signature: sshSign(s.key, Buffer.from(text), REPORT_ACK_NAMESPACE), activeRulesCommit: null }), 'REPORT_NOT_RECIPIENT');
  refuses(() => s.gate.verifyReportAck({ tenantId: TENANT, reportId: rep, reportSha256: sum, ticketText: text,
    signature: sshSign(s.key, Buffer.from(text), RULES_NAMESPACE), activeRulesCommit: null }), 'RULES_SIGNATURE_INVALID');
});

test('Л.8: проверка перед арендой — чистая копия на origin/main с теми же правилами', () => {
  const s = setup();
  const out = s.gate.checkWorkingCopy(s.r.head);
  assert.deepEqual(out, { code_commit: s.r.merge, rules_commit: s.r.head });
  s.r.put('stray.txt', 'x');
  refuses(() => s.gate.checkWorkingCopy(s.r.head), 'RULES_WORKTREE_DIRTY');
  s.r.g('add', '-A');
  s.r.g('commit', '-q', '-m', 'local');
  refuses(() => s.gate.checkWorkingCopy(s.r.head), 'RULES_HEAD_NOT_MAIN');
  const changed = setup({ changeRulesInMerge: true });
  refuses(() => changed.gate.checkWorkingCopy(changed.r.head), 'RULES_WORKTREE_DIFFERS');
  refuses(() => s.gate.checkWorkingCopy(null), 'LEASE_NO_ACTIVE_RULES');
});

test('Z-RULES-01: реестр — опасные пути, петли и роли без пути к оператору отклоняются', () => {
  const reg = (over) => Buffer.from(JSON.stringify({ format: 'zavod-rules-registry@v1', files: ['AGENTS.md'],
    role_parents: PARENTS, ...over }));
  assert.deepEqual(parseRegistry(reg({})).role_parents, PARENTS);
  for (const files of [['../x'], ['a/../b'], ['/abs'], ['a\\b'], ['a//b'], ['dir/'], ['./a'], [REGISTRY_PATH], ['a', 'a'], []]) {
    refuses(() => parseRegistry(reg({ files })), 'RULES_REGISTRY_BAD');
  }
  refuses(() => parseRegistry(reg({ role_parents: { '01_A': '02_B', '02_B': '01_A' } })), 'RULES_REGISTRY_BAD');
  refuses(() => parseRegistry(reg({ role_parents: { '01_A': '01_A' } })), 'RULES_REGISTRY_BAD');
  refuses(() => parseRegistry(reg({ role_parents: { '01_A': 'NOBODY' } })), 'RULES_REGISTRY_BAD');
  refuses(() => parseRegistry(reg({ role_parents: { 'bad': 'OPERATOR' } })), 'RULES_REGISTRY_BAD');
  refuses(() => parseRegistry(reg({ format: 'other' })), 'RULES_REGISTRY_BAD');
  refuses(() => parseRegistry(Buffer.from('not json')), 'RULES_REGISTRY_BAD');
});
