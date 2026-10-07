// ДОКУМЕНТ: tests/stage_gates.test.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:47 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:47 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: протокол Z1 v1.1 раздел 9 — этап 4 не начинается при OPEN/FAIL у APPROVE этапа 1,
//   E3-4 или E3-5; испорченный файл состояния даёт отказ. База не нужна.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { checkStage, validateGates } from '../src/stage_gates.mjs';

const FILE = fileURLToPath(new URL('../zavod_stage_gates.json', import.meta.url));
const load = () => JSON.parse(readFileSync(FILE, 'utf8'));
const passAll = (g, sid) => { for (const c of Object.values(g.stages[sid].criteria)) { c.status = 'PASS'; c.evidence = 'test'; } };

test('файл состояния корректен', () => {
  assert.deepEqual(validateGates(load()), []);
});

test('этап 4 сейчас запрещён: APPROVE этапа 1, E3-4, E3-5 не PASS', () => {
  const r = checkStage(load(), 4);
  assert.equal(r.allow, false);
  for (const b of ['1:APPROVE=OPEN', '3:E3-4=OPEN', '3:E3-5=OPEN']) assert.ok(r.blockers.includes(b), b);
});

test('этап 4 разрешён, только когда всё требуемое PASS', () => {
  const g = load(); passAll(g, '1'); passAll(g, '3');
  assert.equal(checkStage(g, 4).allow, true);
  for (const [sid, cid] of [['1', 'APPROVE'], ['3', 'E3-4'], ['3', 'E3-5']]) {
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

test('командная строка: DENY и код 1 для этапа 4', () => {
  const p = spawnSync(process.execPath, [fileURLToPath(new URL('../src/stage_gates.mjs', import.meta.url)), FILE, '4'], { encoding: 'utf8' });
  assert.equal(p.status, 1);
  assert.match(p.stdout, /STAGE_GATE=DENY stage=4 phase=start/);
});
