// ДОКУМЕНТ: ci/engine/p05b_after_restart.mjs
// ВЕРСИЯ: v1.0
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-06 19:55 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия 4401918c-de88-4db7-841e-b418568ae069)
// НАЗНАЧЕНИЕ: проба п.5 на PostgreSQL, часть 2 (перенос R47 p05b): после жёсткого убийства и перезапуска
//   экземпляр жив, B получает ту же работу, эффект один, процесс доходит до конца. Итог — p05_result.json.
import { readFileSync, writeFileSync } from "node:fs";
import { S, api, log, setLog, acquire, completeJob, executions, procInstances, sleep, vars } from "./lib.mjs";

setLog(`${S}/p05.log`);
log("=== p05b", new Date().toISOString());
async function waitFor(fn, what, ms = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { const v = await fn().catch(() => null); if (v) return v; await sleep(500); }
  log(`  !! не дождались: ${what}`); return null;
}
const acts = async (pid) => (await executions({ processInstanceId: pid })).filter((e) => e.activityId).map((e) => e.activityId).sort();
const st = JSON.parse(readFileSync(`${S}/p05_state.json`, "utf8"));
const effFile = `${S}/p05_effects.json`;
const adapter = (key, who) => {
  const e = JSON.parse(readFileSync(effFile, "utf8"));
  if (!e[key]) { e[key] = { by: who, at: new Date().toISOString() }; writeFileSync(effFile, JSON.stringify(e, null, 1)); }
  return { effect: e[key], total: Object.keys(e).length };
};
const res = { alive: false, sameJob: false, effectBy: null, effectsTotal: null, reachedEnd: false };
res.alive = (await procInstances({ id: st.pid })).length === 1;
log("p05 экземпляр после перезапуска жив:", res.alive, "; активности:", await acts(st.pid));
const t0 = Date.now(); let B = null;
while (!B && Date.now() - t0 < 240000) {
  B = ((await acquire("exec-anthropic", "w-B", "PT60S").catch(() => ({ json: [] }))).json ?? []).find((j) => j.processInstanceId === st.sp) ?? null;
  if (!B) await sleep(2000);
}
res.sameJob = B?.id === st.jobId;
log("p05 B получил работу через", Math.round((Date.now() - t0) / 1000), "с; тот же id:", res.sameJob, "; аренда A была до", st.lockExp);
if (B) {
  const r = adapter(st.key, "B");
  res.effectBy = r.effect.by;
  log("p05 адаптер B: эффект от", r.effect.by, "; эффектов всего", r.total);
  log("p05 complete B:", (await completeJob(B.id, "w-B")).status);
  const ex = await waitFor(async () => (await executions({ processInstanceId: st.sp })).find((e) => e.activityId === "s3"), "s3");
  if (ex) await api("PUT", `/service/runtime/executions/${ex.id}`, { action: "messageEventReceived", messageName: "subtaskAck" });
  const kernel = async (topic, el) => {
    await waitFor(async () => (await acts(st.pid)).includes(el), el);
    for (let i = 0; i < 20; i++) { const js = (await acquire(topic, "kernel-w")).json ?? []; for (const x of js) await completeJob(x.id, "kernel-w"); if (js.length) return; await sleep(500); }
  };
  await kernel("kernel", "n8"); await kernel("kernel", "n9");
  await kernel("kernel-check", "n11"); await kernel("kernel-publish", "n12"); await kernel("kernel-assign", "n14");
  const n15 = await waitFor(async () => (await executions({ processInstanceId: st.pid, activityId: "n15" }))[0], "n15");
  if (n15) await api("PUT", `/service/runtime/executions/${n15.id}`, { action: "trigger", variables: vars({ verdict: "ACCEPT" }) });
  await kernel("kernel", "n17"); await kernel("egress", "n18");
  res.reachedEnd = !!(await waitFor(async () => (await procInstances({ id: st.pid })).length === 0, "конец"));
}
res.effectsTotal = Object.keys(JSON.parse(readFileSync(effFile, "utf8"))).length;
log("p05 процесс дошёл до конца:", res.reachedEnd, "; эффектов в журнале:", res.effectsTotal);
writeFileSync(`${S}/p05_result.json`, JSON.stringify(res, null, 1));
const ok = res.alive && res.sameJob && res.effectBy === "A" && res.effectsTotal === 1 && res.reachedEnd;
log("=== p05b end; P05_RESULT=" + (ok ? "PASS" : "FAIL"));
process.exit(ok ? 0 : 1);
