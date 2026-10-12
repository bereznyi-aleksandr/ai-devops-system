// ДОКУМЕНТ: zavod/engine/ci/stall_diag.mjs
// ВЕРСИЯ: v0.3  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 11:04 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-12 13:43 +03:00 (v0.3: аудит ChatGPT S6-prep R4, L-S6-R4-01 —
//   stallWatch стал пассивным: ничего не качает (orch.pump больше не вызывается) и в движок не пишет; до 150 с раз в
//   2 с читает базой движка блокировки исполнений и внешних заданий (только SELECT) и пишет, когда блокировка
//   экземпляра снялась (STALL_LOCK_CLEARED) или что держалась до конца (STALL_LOCK_HELD); о «сдвиге экземпляра»
//   ничего не утверждает. v0.2: CI 38225551966 прогон 1 поймал
//   зависание: заказ B стоит на n8, внешнее задание без владельца и без срока блокировки, 60 с ни один захват его не
//   взял. REST движка блокировку экземпляра (ACT_RU_EXECUTION.LOCK_TIME_/LOCK_OWNER_) не показывает — sqlDiag
//   читает её прямо из базы движка (только SELECT) вместе со строками ACT_RU_EXTERNAL_JOB; stallWatch после
//   «не дождались» качает дальше и пишет, через сколько секунд экземпляр сдвинулся сам)
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: только диагностика CI. На ai-devops-system dc06d397 и 4b235aa0 проверки E4-3/E4-4 в одном из трёх
//   повторов не дождались узла n15 (60–90 с без продвижения; обычно 7 с), а журнал не говорил, где стоит экземпляр.
//   stallDiag снимает состояние всех активных экземпляров bem_work/bem_subtask: на каком узле стоят исполнения,
//   какие задания движка есть (асинхронные, таймеры, внешние с владельцем блокировки, мёртвые с текстом ошибки).
//   Ничего не меняет в движке: только GET.
// ОГРАНИЧЕНИЯ: вывод — JSON без переменных процессов (в них может быть текст заявки); текст ошибок обрезан до 300 знаков.
import { createRequire } from 'node:module';

const cut = (s) => (s == null ? s : String(s).slice(0, 300));
const LOCKISH = /^(id_|rev_|proc_inst_id_|process_instance_id_|parent_id_|act_id_|element_id_|is_active_|is_scope_|is_concurrent_|lock_time_|lock_owner_|lock_exp_time_|exclusive_|retries_|create_time_|job_handler_type_|scope_type_)$/;
const pick = (row) => Object.fromEntries(Object.entries(row).filter(([k]) => LOCKISH.test(k)));

// Только SELECT из базы движка (стенд CI: база bem_engine_e43, схема bem_engine, пользователь postgres без пароля).
// Ошибка подключения или запроса не роняет проверку — попадает в вывод как текст.
export async function sqlDiag(pids) {
  try {
    const pg = createRequire(new URL('../../kernel/package.json', import.meta.url))('pg');
    const c = new pg.Client({ host: process.env.PGHOST || '127.0.0.1', port: Number(process.env.PGPORT || 5432),
      database: process.env.ZAVOD_ENGINE_DB || 'bem_engine_e43', user: process.env.ZAVOD_ENGINE_DB_USER || 'postgres' });
    await c.connect();
    try {
      const now = (await c.query('SELECT now() AS now')).rows[0].now;
      const ex = (await c.query('SELECT * FROM bem_engine.act_ru_execution WHERE proc_inst_id_ = ANY($1)', [pids])).rows.map(pick);
      const xj = (await c.query('SELECT * FROM bem_engine.act_ru_external_job WHERE process_instance_id_ = ANY($1)', [pids])).rows.map(pick);
      return { db_now: now, executions: ex, external_jobs: xj };
    } finally { await c.end(); }
  } catch (e) {
    return { sql_error: cut(e?.message) };
  }
}

// После «не дождались» — только наблюдение (L-S6-R4-01): ничего не качает и в движок не пишет. До extraMs раз в
// 2 с читает блокировки (sqlDiag, только SELECT). Блокировки исполнений (lock_time_) пропали —
// STALL_LOCK_CLEARED с секундами от начала ожидания; держались до конца — STALL_LOCK_HELD. Итог проверки не
// меняется — она уже провалена.
const locks = (d) => (d.executions || []).filter((e) => e.lock_time_ != null).map((e) => `${e.id_}@${e.lock_time_}`).sort().join(',');
export async function stallWatch({ t0, extraMs = 150000, sleep, log, pids }) {
  const first = await sqlDiag(pids);
  const held = locks(first);
  const until = Date.now() + extraMs;
  let last = first;
  while (held && Date.now() < until) {
    await sleep(2000);
    last = await sqlDiag(pids);
    if (locks(last) !== held) {
      log(`  STALL_LOCK_CLEARED after ${Math.round((Date.now() - t0) / 1000)} s ${JSON.stringify(last)}`);
      return true;
    }
  }
  log(`  STALL_LOCK_HELD after ${Math.round((Date.now() - t0) / 1000)} s held=${held || 'none'} ${JSON.stringify(last)}`);
  return false;
}

async function list(engine, path) {
  const r = await engine.api('GET', path);
  return r.status === 200 ? (r.json?.data ?? r.json ?? []) : [{ http: r.status, text: cut(r.text) }];
}

export async function stallDiag(engine) {
  const out = { at: new Date().toISOString(), instances: [] };
  for (const key of ['bem_work', 'bem_subtask']) {
    for (const pi of await list(engine, `/service/runtime/process-instances?processDefinitionKey=${key}&size=50`)) {
      if (!pi.id) { out.instances.push({ key, error: pi }); continue; }
      const q = `processInstanceId=${pi.id}&size=50`;
      out.instances.push({
        key, pid: pi.id, suspended: pi.suspended, ended: pi.ended,
        executions: (await list(engine, `/service/runtime/executions?${q}`)).map((e) => e.activityId ?? null).filter(Boolean),
        jobs: (await list(engine, `/service/management/jobs?${q}`)).map((j) => ({ id: j.id, retries: j.retries, due: j.dueDate, exc: cut(j.exceptionMessage), el: j.elementId })),
        timers: (await list(engine, `/service/management/timer-jobs?${q}`)).map((j) => ({ id: j.id, due: j.dueDate, el: j.elementId })),
        deadletter: (await list(engine, `/service/management/deadletter-jobs?${q}`)).map((j) => ({ id: j.id, exc: cut(j.exceptionMessage), el: j.elementId })),
        external: (await list(engine, `/external-job-api/jobs?${q}`)).map((j) => ({ id: j.id, el: j.elementId, owner: j.lockOwner, until: j.lockExpirationTime, retries: j.retries, exc: cut(j.exceptionMessage) })),
      });
    }
  }
  out.sql = await sqlDiag(out.instances.map((i) => i.pid).filter(Boolean));
  return out;
}
