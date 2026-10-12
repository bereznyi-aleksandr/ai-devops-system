// ДОКУМЕНТ: zavod/engine/ci/stall_diag.mjs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-12 11:04 +03:00
// ИСПОЛНИТЕЛЬ: Claude (ГД Завода, сессия 9951b86f-676a-4a39-84f8-eeef3f226cd1)
// НАЗНАЧЕНИЕ: только диагностика CI. На ai-devops-system dc06d397 и 4b235aa0 проверки E4-3/E4-4 в одном из трёх
//   повторов не дождались узла n15 (60–90 с без продвижения; обычно 7 с), а журнал не говорил, где стоит экземпляр.
//   stallDiag снимает состояние всех активных экземпляров bem_work/bem_subtask: на каком узле стоят исполнения,
//   какие задания движка есть (асинхронные, таймеры, внешние с владельцем блокировки, мёртвые с текстом ошибки).
//   Ничего не меняет в движке: только GET.
// ОГРАНИЧЕНИЯ: вывод — JSON без переменных процессов (в них может быть текст заявки); текст ошибок обрезан до 300 знаков.
const cut = (s) => (s == null ? s : String(s).slice(0, 300));

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
  return out;
}
