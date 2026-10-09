// ДОКУМЕНТ: src/stage_gates.mjs
// ВЕРСИЯ: v0.2  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:47 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-08 22:55 +03:00 (v0.2: аудит E3-5 M-E35-03 —
//   файл состояния сверяется с неизменяемым каноном в коде: точный набор этапов и критериев,
//   точные start_requires/release_requires; удаление, добавление или правка — INVALID, отказ)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: механическая проверка зависимостей этапов (протокол Z1 v1.1, раздел 9):
//   этап нельзя начать, пока любой требуемый критерий не PASS. Ошибка в файле состояния —
//   отказ, а не «разрешено». Вызов: node src/stage_gates.mjs <файл> <этап> -> STAGE_GATE=ALLOW|DENY.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const STATUSES = new Set(['PASS', 'FAIL', 'OPEN']);

// Канон протокола Z1 (раздел 9). Файл состояния меняет только статусы и доказательства;
// состав критериев и зависимости меняются только правкой этого кода (ревью и аудит).
export const CANON = Object.freeze({
  1: { criteria: ['APPROVE'], start: [], release: [] },
  2: { criteria: ['E2-1', 'E2-2', 'E2-3', 'E2-4', 'E2-5'], start: [], release: [] },
  3: { criteria: ['E3-1', 'E3-2', 'E3-3', 'E3-4a', 'E3-4b', 'E3-5'], start: [], release: [] },
  4: { criteria: ['E4-1', 'E4-2', 'E4-3', 'E4-4', 'E4-5', 'E4-6', 'E4-7', 'E4-8', 'OD-8', 'OD-2'],
    start: ['1:APPROVE', '3:*'], release: [] },
  5: { criteria: ['E5-1', 'E5-2', 'E5-3', 'E5-4', 'E5-5', 'E5-6', 'E5-7', 'OD-3', 'OD-4'], start: ['4:*'], release: [] },
  6: { criteria: ['E6-1', 'E6-2', 'E6-3', 'E6-4', 'E6-5', 'OD-5'], start: ['4:*'], release: ['5:*'] },
  7: { criteria: ['E7-2', 'E7-3', 'E7-4', 'OD-6'], start: ['6:*'], release: [] },
});

const sameSet = (a, b) => a.length === b.length && [...a].sort().join('\n') === [...b].sort().join('\n');

// M-E35-03: сверка с каноном. Любое расхождение — ошибка (а не «этого требования нет»).
export function canonErrors(gates) {
  const errors = [];
  const stages = gates?.stages;
  if (!stages || typeof stages !== 'object') return ['stages missing'];
  if (!sameSet(Object.keys(stages), Object.keys(CANON))) errors.push('stage set differs from canon');
  for (const [sid, canon] of Object.entries(CANON)) {
    const st = stages[sid];
    if (!st || typeof st !== 'object') { errors.push(`${sid}: stage missing`); continue; }
    const crit = st.criteria && typeof st.criteria === 'object' ? Object.keys(st.criteria) : [];
    if (!sameSet(crit, canon.criteria)) errors.push(`${sid}: criteria differ from canon`);
    for (const [key, want] of [['start_requires', canon.start], ['release_requires', canon.release]]) {
      const have = st[key] === undefined ? [] : st[key];
      if (!Array.isArray(have) || !sameSet(have.map(String), want)) errors.push(`${sid}: ${key} differs from canon`);
    }
  }
  return errors;
}

// Проверка формы файла: неизвестный статус, PASS без доказательства, ссылка на
// несуществующий этап или критерий — ошибки. Возвращает список ошибок.
export function validateGates(gates) {
  const errors = canonErrors(gates);
  const stages = gates?.stages;
  if (!stages || typeof stages !== 'object') return errors;
  for (const [sid, st] of Object.entries(stages)) {
    const crit = st?.criteria;
    if (!crit || typeof crit !== 'object' || !Object.keys(crit).length) { errors.push(`${sid}: no criteria`); continue; }
    for (const [cid, c] of Object.entries(crit)) {
      if (!STATUSES.has(c?.status)) errors.push(`${sid}:${cid}: bad status`);
      if (c?.status === 'PASS' && !(typeof c.evidence === 'string' && c.evidence.trim())) errors.push(`${sid}:${cid}: PASS without evidence`);
    }
    for (const key of ['start_requires', 'release_requires']) {
      if (st[key] === undefined) continue;
      if (!Array.isArray(st[key])) { errors.push(`${sid}: ${key} not a list`); continue; }
      for (const ref of st[key]) {
        const [rs, rc] = String(ref).split(':');
        if (!stages[rs]) errors.push(`${sid}: ${key} unknown stage ${rs}`);
        else if (rc !== '*' && !stages[rs].criteria?.[rc]) errors.push(`${sid}: ${key} unknown criterion ${ref}`);
      }
    }
  }
  return errors;
}

function blockersOf(gates, refs) {
  const out = [];
  for (const ref of refs) {
    const [rs, rc] = ref.split(':');
    const crit = gates.stages[rs].criteria;
    const ids = rc === '*' ? Object.keys(crit) : [rc];
    for (const id of ids) if (crit[id].status !== 'PASS') out.push(`${rs}:${id}=${crit[id].status}`);
  }
  return out;
}

// phase: 'start' (начать этап) или 'release' (выпуск этапа, где задан release_requires).
export function checkStage(gates, stageId, phase = 'start') {
  const errors = validateGates(gates);
  if (errors.length) return { allow: false, blockers: errors.map(e => `INVALID ${e}`) };
  const st = gates.stages[String(stageId)];
  if (!st) return { allow: false, blockers: [`INVALID unknown stage ${stageId}`] };
  const refs = phase === 'release' ? [...(st.start_requires ?? []), ...(st.release_requires ?? [])] : (st.start_requires ?? []);
  const blockers = blockersOf(gates, refs);
  return { allow: blockers.length === 0, blockers };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [file, stage, phase = 'start'] = process.argv.slice(2);
  let gates;
  try { gates = JSON.parse(readFileSync(file, 'utf8')); } catch { console.log('STAGE_GATE=DENY reason=unreadable'); process.exit(2); }
  const r = checkStage(gates, stage, phase);
  for (const b of r.blockers) console.log(`blocker ${b}`);
  console.log(`STAGE_GATE=${r.allow ? 'ALLOW' : 'DENY'} stage=${stage} phase=${phase}`);
  process.exit(r.allow ? 0 : 1);
}
