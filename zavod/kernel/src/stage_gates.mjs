// ДОКУМЕНТ: src/stage_gates.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 13:47 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 13:47 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: механическая проверка зависимостей этапов (протокол Z1 v1.1, раздел 9):
//   этап нельзя начать, пока любой требуемый критерий не PASS. Ошибка в файле состояния —
//   отказ, а не «разрешено». Вызов: node src/stage_gates.mjs <файл> <этап> -> STAGE_GATE=ALLOW|DENY.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const STATUSES = new Set(['PASS', 'FAIL', 'OPEN']);

// Проверка формы файла: неизвестный статус, PASS без доказательства, ссылка на
// несуществующий этап или критерий — ошибки. Возвращает список ошибок.
export function validateGates(gates) {
  const errors = [];
  const stages = gates?.stages;
  if (!stages || typeof stages !== 'object') return ['stages missing'];
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
