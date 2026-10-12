// ДОКУМЕНТ: tests/authorship_check.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-09 13:20 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-09 13:20 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: E5-2 (W2) — проверка авторства по выгрузке: автор-рабочий и пара ACCEPT {anthropic, openai} от
//   не-авторов — PASS; автор-человек, вердикт автора, вердикт человека, неполная пара, чужие строки — отказ;
//   вердикт старой версии не считается; сумма выгрузки не зависит от порядка строк.
// ОГРАНИЧЕНИЯ: без базы; на живом предмете Kernel выгрузку проверяет tests/release_egress.test.mjs.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { checkAuthorship } from '../src/authorship_check.mjs';

const S = randomUUID();
const HEAD = 'c'.repeat(40);
const base = () => ({
  subject: { id: S, head_sha: HEAD, scope: 'ZAVOD_PRODUCT_RELEASE' },
  authors: [{ subject_id: S, actor_id: 'claude:worker-1', provider: 'anthropic' }],
  verdicts: [
    { id: randomUUID(), subject_id: S, head_sha: HEAD, auditor_actor: 'codex:aud-1', auditor_provider: 'openai', verdict: 'ACCEPT' },
    { id: randomUUID(), subject_id: S, head_sha: HEAD, auditor_actor: 'claude:aud-1', auditor_provider: 'anthropic', verdict: 'ACCEPT' },
  ],
});

test('E5-2 автор-рабочий, пара ACCEPT от не-авторов — PASS', () => {
  const r = checkAuthorship(base());
  assert.deepEqual(r.problems, []);
  assert.match(r.sha256, /^[0-9a-f]{64}$/);
});

test('E5-2 вердикт автора по действующей версии — SELF_REVIEW', () => {
  const x = base(); x.verdicts[1].auditor_actor = 'claude:worker-1';
  assert.ok(checkAuthorship(x).problems.includes('SELF_REVIEW claude:worker-1'));
});

test('E5-2 автор — человек, а не рабочий — NOT_A_WORKER', () => {
  const x = base(); x.authors.push({ subject_id: S, actor_id: 'human:operator', provider: 'human' });
  assert.ok(checkAuthorship(x).problems.includes('NOT_A_WORKER human:operator'));
});

test('E5-2 вердикт человека и неполная пара — отказ', () => {
  const x = base(); x.verdicts[0] = { ...x.verdicts[0], auditor_actor: 'human:operator', auditor_provider: 'human' };
  const p = checkAuthorship(x).problems;
  assert.ok(p.includes('HUMAN_VERDICT human:operator'));
  assert.ok(p.includes('ACCEPT_PROVIDERS anthropic,human'));
  const y = base(); y.verdicts.pop();
  assert.deepEqual(checkAuthorship(y).problems, ['ACCEPT_PROVIDERS openai']);
});

test('E5-2 нет авторов, нет предмета, чужие строки — отказ', () => {
  const x = base(); x.authors = [];
  assert.ok(checkAuthorship(x).problems.includes('NO_AUTHOR'));
  assert.deepEqual(checkAuthorship({ ...base(), subject: null }).problems, ['NO_SUBJECT']);
  const y = base(); y.verdicts[0].subject_id = randomUUID(); y.authors[0].subject_id = randomUUID();
  const p = checkAuthorship(y).problems;
  assert.ok(p.some((s) => s.startsWith('FOREIGN_VERDICT_ROW ')));
  assert.ok(p.some((s) => s.startsWith('FOREIGN_AUTHOR_ROW ')));
});

test('E5-2 вердикт автора по старой версии не действует; сумма не зависит от порядка', () => {
  const x = base();
  x.verdicts.push({ id: randomUUID(), subject_id: S, head_sha: 'd'.repeat(40), auditor_actor: 'claude:worker-1',
    auditor_provider: 'anthropic', verdict: 'ACCEPT' });
  const a = checkAuthorship(x);
  assert.deepEqual(a.problems, []);
  const b = checkAuthorship({ ...x, verdicts: [...x.verdicts].reverse() });
  assert.equal(a.sha256, b.sha256);
  const c = base(); c.verdicts[0].auditor_actor = 'codex:aud-2';
  assert.notEqual(checkAuthorship(c).sha256, checkAuthorship(base()).sha256);
});
