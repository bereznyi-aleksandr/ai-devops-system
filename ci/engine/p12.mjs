// ДОКУМЕНТ: ci/engine/p12.mjs
// ВЕРСИЯ: v1.0
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 06:30 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия f19e07a7-6edd-48a5-9ede-88086c949326)
// НАЗНАЧЕНИЕ: пункт 12 раздела 22 на PostgreSQL (перенос R47 p06_p12 v1.0, с ожидаемым итогом):
//   (а) сигнал 2 — исполнитель openai стоит, работа без владельца старше порога найдена;
//   (в) сигнал 3 — сверка списка работ Kernel (заглушка) с живыми экземплярами: работа без экземпляра и экземпляр без работы.
//   (б) сигнал 1 — опрос health при убитом движке — в ci/engine_pg_probes.sh.
// ОГРАНИЧЕНИЯ: экземпляры не удаляются; «удалённый экземпляр» — запись работы со ссылкой на несуществующий экземпляр.
import { api, log, setLog, check, S, startByMessage, acquire, completeJob, procInstances, sleep, waitFor, acts } from "./lib.mjs";

setLog(`${S}/p12.log`);
log("=== p12a/p12c", new Date().toISOString());

const BK = "W-CI-12a";
const pid = (await startByMessage("bemIntake", { subtaskCount: 1, providers: "openai", workKey: BK, authorsJson: "[]" }, BK)).json.id;
for (const el of ["n2", "n3", "n4", "n6"]) {
  await waitFor(async () => (await acts(pid)).includes(el), el);
  for (let i = 0; i < 40; i++) {
    const js = (await acquire("kernel", "kernel-w")).json ?? [];
    for (const x of js) await completeJob(x.id, "kernel-w", x.elementId === "n4" ? { criticality: "NORMAL" } : {});
    if (js.some((x) => x.processInstanceId === pid && x.elementId === el)) break;
    await sleep(500);
  }
}
const sp = (await waitFor(async () => { const q = await procInstances({ superProcessInstanceId: pid }); return q.length ? q : null; }, "sub"))?.[0]?.id;
await sleep(25000);
const THRESHOLD_S = 20;
const list = await api("GET", "/external-job-api/jobs?size=200");
const stale = (list.json?.data ?? []).filter((j) => !j.lockOwner && (Date.now() - Date.parse(j.createTime)) / 1000 > THRESHOLD_S);
check("p12a_signal2_stale_job", list.status === 200 && stale.some((j) => j.processInstanceId === sp), { listStatus: list.status, stale: stale.map((j) => `${j.elementId}@${j.processInstanceId === sp ? "W-CI-12a" : "другой"}`) });

const live = await procInstances({ processDefinitionKey: "bem_work" });
const kernelWork = [
  ...live.filter((p) => p.businessKey).map((p) => ({ workKey: p.businessKey, pid: p.id, status: "IN_PROGRESS" })),
  { workKey: "W-CI-GONE", pid: "00000000-0000-0000-0000-000000000000", status: "IN_PROGRESS" },
];
const liveIds = new Set(live.map((p) => p.id));
const lost = kernelWork.filter((w) => w.status === "IN_PROGRESS" && !liveIds.has(w.pid));
const orphans = live.filter((p) => !kernelWork.some((w) => w.pid === p.id));
check("p12c_signal3_work_without_instance", lost.length === 1 && lost[0].workKey === "W-CI-GONE", { lost: lost.map((w) => w.workKey) });
check("p12c_signal3_instance_without_work", orphans.length >= 1, { orphans: orphans.length, note: "старт по ключу без сообщения (p02_p14)" });
log("=== p12 end");
