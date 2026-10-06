// ДОКУМЕНТ: ci/engine/p05a_before_kill.mjs
// ВЕРСИЯ: v1.0
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-06 19:55 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия 4401918c-de88-4db7-841e-b418568ae069)
// НАЗНАЧЕНИЕ: проба п.5 раздела 22 на PostgreSQL, часть 1 (перенос R47 p05a): развернуть bem_work,
//   довести экземпляр до s2, исполнитель A захватывает работу и записывает эффект; затем задание убивает java.
import { readFileSync, writeFileSync } from "node:fs";
import { S, log, setLog, deploy, startByMessage, acquire, completeJob, executions, procInstances, sleep } from "./lib.mjs";

setLog(`${S}/p05.log`);
writeFileSync(`${S}/p05.log`, "");
log("=== p05a", new Date().toISOString());
async function waitFor(fn, what, ms = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { const v = await fn(); if (v) return v; await sleep(400); }
  log(`  !! не дождались: ${what}`); return null;
}
const d = await deploy("bem_work.bpmn20.xml", readFileSync(new URL("./bem_work.bpmn20.xml", import.meta.url), "utf8"));
log("p05 deploy:", d.status);
if (d.status !== 201) { log(d.text); process.exit(2); }
const acts = async (pid) => (await executions({ processInstanceId: pid })).filter((e) => e.activityId).map((e) => e.activityId).sort();
const BK = "W-CI-5";
const pid = (await startByMessage("bemIntake", { subtaskCount: 1, providers: "anthropic", workKey: BK, authorsJson: "[]" }, BK)).json.id;
for (const el of ["n2", "n3", "n4", "n6"]) {
  await waitFor(async () => (await acts(pid)).includes(el), el);
  for (const x of (await acquire("kernel", "kernel-w")).json ?? []) await completeJob(x.id, "kernel-w", el === "n4" ? { criticality: "NORMAL" } : {});
}
const sp = (await waitFor(async () => { const q = await procInstances({ superProcessInstanceId: pid }); return q.length ? q : null; }, "sub"))[0].id;
let ja = [];
for (let i = 0; i < 60 && !ja.length; i++) { ja = ((await acquire("exec-anthropic", "w-A", "PT30S")).json ?? []).filter((j) => j.processInstanceId === sp); if (!ja.length) await sleep(500); }
if (!ja.length) { log("  !! A не получил работу"); process.exit(3); }
const key = `${sp}|s2|0`;
writeFileSync(`${S}/p05_effects.json`, JSON.stringify({ [key]: { by: "A", at: new Date().toISOString() } }, null, 1));
writeFileSync(`${S}/p05_state.json`, JSON.stringify({ pid, sp, jobId: ja[0].id, key, lockExp: ja[0].lockExpirationTime }, null, 1));
log("p05 A захватил", ja[0].id, "до", ja[0].lockExpirationTime, "; адаптер: эффект записан; ключ", key);
log("=== p05a end — дальше убить java");
