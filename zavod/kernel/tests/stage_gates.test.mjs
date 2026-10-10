// ДОКУМЕНТ: tests/stage_gates.test.mjs
// ВЕРСИЯ: v0.5  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:47 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-10 14:38 +03:00 (v0.5: файл состояния v1.0 —
//   OD-2 PASS, этап 5 запрещён до E4-2; v0.4: файл состояния v0.5 —
//   этап 4 разрешён, этап 5 запрещён до OD-2; v0.3: аудит E3-5 M-E35-03 —
//   удаление, добавление или правка обязательного критерия или зависимости — INVALID, отказ; v0.2: E3-4a/E3-4b, OD-2)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf, до v0.4; сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1, v0.5)
// НАЗНАЧЕНИЕ: протокол Z1 v1.2 раздел 9 — этап 4 не начинается при OPEN/FAIL у APPROVE этапа 1,
//   E3-4a, E3-4b (гейт OD-1a) или E3-5; этап 5 — при OPEN у OD-2 или OD-8; испорченный файл — отказ.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkStage, validateGates, CANON } from '../src/stage_gates.mjs';

const FILE = fileURLToPath(new URL('../zavod_stage_gates.json', import.meta.url));
const load = () => JSON.parse(readFileSync(FILE, 'utf8'));
const passAll = (g, sid) => { for (const c of Object.values(g.stages[sid].criteria)) { c.status = 'PASS'; c.evidence = 'test'; } };

test('файл состояния корректен', () => {
  assert.deepEqual(validateGates(load()), []);
});

test('сейчас: этап 4 разрешён (этапы 1 и 3 PASS), этап 5 запрещён — E4-2 OPEN, OD-2 PASS', () => {
  assert.deepEqual(checkStage(load(), 4), { allow: true, blockers: [] });
  const r = checkStage(load(), 5);
  assert.equal(r.allow, false);
  assert.ok(r.blockers.includes('4:E4-2=OPEN'), r.blockers.join(';'));
  assert.ok(!r.blockers.some((b) => b.startsWith('4:OD-2=')), r.blockers.join(';'));
});

test('этап 4 разрешён, только когда всё требуемое PASS', () => {
  const g = load(); passAll(g, '1'); passAll(g, '3');
  assert.equal(checkStage(g, 4).allow, true);
  for (const [sid, cid] of [['1', 'APPROVE'], ['3', 'E3-4a'], ['3', 'E3-4b'], ['3', 'E3-5']]) {
    for (const bad of ['OPEN', 'FAIL']) {
      const h = structuredClone(g); h.stages[sid].criteria[cid].status = bad;
      const r = checkStage(h, 4);
      assert.equal(r.allow, false, `${sid}:${cid}=${bad}`);
      assert.deepEqual(r.blockers, [`${sid}:${cid}=${bad}`]);
    }
  }
});

test('выпуск этапа 6 требует закрытого этапа 5, начало — нет', () => {
  const g = load(); for (const s of ['1', '3', '4']) passAll(g, s);
  assert.equal(checkStage(g, 6, 'start').allow, true);
  assert.equal(checkStage(g, 6, 'release').allow, false);
  passAll(g, '5');
  assert.equal(checkStage(g, 6, 'release').allow, true);
});

test('испорченный файл — отказ, а не разрешение', () => {
  const cases = [
    g => { g.stages['1'].criteria.APPROVE.status = 'DONE'; },
    g => { passAll(g, '1'); passAll(g, '3'); delete g.stages['3'].criteria['E3-2'].evidence; },
    g => { g.stages['4'].start_requires.push('9:*'); },
    g => { g.stages['4'].start_requires.push('3:E3-9'); },
    g => { delete g.stages; },
  ];
  for (const mutate of cases) {
    const g = load(); passAll(g, '1'); passAll(g, '3'); mutate(g);
    const r = checkStage(g, 4);
    assert.equal(r.allow, false);
    assert.ok(r.blockers.every(b => b.startsWith('INVALID')), r.blockers.join(';'));
  }
  assert.equal(checkStage(load(), 42).allow, false);
});

test('командная строка: DENY и код 1 для этапа 5, ALLOW и код 0 для этапа 4', () => {
  const run = (st) => spawnSync(process.execPath, [fileURLToPath(new URL('../src/stage_gates.mjs', import.meta.url)), FILE, st], { encoding: 'utf8' });
  const p = run('5');
  assert.equal(p.status, 1);
  assert.match(p.stdout, /STAGE_GATE=DENY stage=5 phase=start/);
  const q = run('4');
  assert.equal(q.status, 0);
  assert.match(q.stdout, /STAGE_GATE=ALLOW stage=4 phase=start/);
});

test('этап 5 не начинается без OD-2 (изоляция) и OD-8 (движок), даже если E4-1…E4-8 PASS', () => {
  const g = load(); for (const s of ['1', '3', '4']) passAll(g, s);
  assert.equal(checkStage(g, 5).allow, true);
  for (const od of ['OD-2', 'OD-8']) {
    const h = structuredClone(g); h.stages['4'].criteria[od].status = 'OPEN';
    assert.deepEqual(checkStage(h, 5).blockers, [`4:${od}=OPEN`]);
  }
});

test('M-E35-03 удаление или правка обязательного критерия или зависимости — отказ, а не разрешение', () => {
  const ready = () => { const g = load(); for (const s of ['1', '3', '4']) passAll(g, s); return g; };
  assert.equal(checkStage(ready(), 4).allow, true);
  assert.equal(checkStage(ready(), 5).allow, true);
  const cases = [
    ['удалить 3:E3-5', 4, (g) => { delete g.stages['3'].criteria['E3-5']; }],
    ['удалить 3:E3-4b', 4, (g) => { delete g.stages['3'].criteria['E3-4b']; }],
    ['удалить stage4.start_requires', 4, (g) => { delete g.stages['4'].start_requires; }],
    ['пустой stage4.start_requires', 4, (g) => { g.stages['4'].start_requires = []; }],
    ['убрать 1:APPROVE из зависимостей', 4, (g) => { g.stages['4'].start_requires = ['3:*']; }],
    ['сузить 3:* до одного критерия', 4, (g) => { g.stages['4'].start_requires = ['1:APPROVE', '3:E3-1']; }],
    ['удалить 4:OD-2', 5, (g) => { delete g.stages['4'].criteria['OD-2']; }],
    ['удалить 4:OD-8', 5, (g) => { delete g.stages['4'].criteria['OD-8']; }],
    ['удалить stage5.start_requires', 5, (g) => { delete g.stages['5'].start_requires; }],
    ['удалить stage6.release_requires', 6, (g) => { passAll(g, '5'); g.stages['5'].criteria['E5-1'].status = 'OPEN'; delete g.stages['6'].release_requires; }],
    ['добавить лишний критерий', 4, (g) => { g.stages['3'].criteria['E3-X'] = { status: 'PASS', evidence: 't' }; }],
    ['удалить этап 7', 4, (g) => { delete g.stages['7']; }],
    ['добавить этап 8', 4, (g) => { g.stages['8'] = { name: 'x', criteria: { X: { status: 'PASS', evidence: 't' } }, start_requires: [] }; }],
  ];
  for (const [name, stage, mutate] of cases) {
    const g = ready(); mutate(g);
    const r = checkStage(g, stage, stage === 6 ? 'release' : 'start');
    assert.equal(r.allow, false, name);
    assert.ok(r.blockers.some((b) => b.startsWith('INVALID')), `${name}: ${r.blockers.join(';')}`);
  }
});

test('M-E35-03 канон в коде совпадает с файлом состояния и заморожен', () => {
  const g = load();
  for (const [sid, c] of Object.entries(CANON)) {
    assert.deepEqual(Object.keys(g.stages[sid].criteria).sort(), [...c.criteria].sort(), sid);
  }
  assert.ok(Object.isFrozen(CANON));
});
