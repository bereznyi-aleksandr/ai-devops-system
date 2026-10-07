// ДОКУМЕНТ: ci/engine/p02_p14.mjs
// ВЕРСИЯ: v1.0
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 06:20 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия f19e07a7-6edd-48a5-9ede-88086c949326)
// НАЗНАЧЕНИЕ: пункты 2, 3, 4, 6, 9 и 14 раздела 22 на PostgreSQL (перенос R47 p02_p14 v1.1 и p06 из p06_p12 v1.0, с ожидаемым итогом):
//   прогон графа — 3 подзадачи, развилка n10, слияние n13, подтверждение одной подзадачи; темы exec-* разделены;
//   n15 двигает только trigger; повторный complete отклонён; история даёт время, но не автора перехода.
// ОЖИДАЕМО (как в R47): старт по ключу без сообщения движок принимает (201) — находка R47 повторяется.
import { S, api, log, setLog, check, startByMessage, acquire, completeJob, executions, procInstances, history, sleep, vars, waitFor, acts } from "./lib.mjs";

setLog(`${S}/p02_p14.log`);
log("=== p02/p14/p04/p09/p03/p06", new Date().toISOString());

const varsFor = (el) => (el === "n4" ? { criticality: "NORMAL" } : {});
async function step(topic, pid, expectEl, worker = "kernel-w") {
  for (let i = 0; i < 40; i++) {
    const jobs = (await acquire(topic, worker)).json ?? [];
    if (jobs.length) {
      const out = [];
      for (const j of jobs) out.push({ el: j.elementId, mine: j.processInstanceId === pid, st: (await completeJob(j.id, worker, varsFor(j.elementId))).status });
      log(`  ${topic}:`, out.map((x) => `${x.el}${x.mine ? "" : "(чужой)"}=${x.st}`).join(" "));
      if (out.some((x) => x.mine && x.el === expectEl)) return out;
    }
    await sleep(500);
  }
  log(`  ${topic}: работы ${expectEl} нет за 20 с`);
  return [];
}

// п.4 (часть): старт по ключу, а не сообщением.
const byKey = await api("POST", "/service/runtime/process-instances", { processDefinitionKey: "bem_work", variables: vars({ subtaskCount: 1 }) });
check("p04_start_by_key_accepted_R47_finding", byKey.status === 201, `старт по ключу без сообщения: ${byKey.status}`);

const BK = "W-CI-2";
const st = await startByMessage("bemIntake", { subtaskCount: 3, providers: "anthropic,openai,anthropic", workKey: BK, authorsJson: "[]" }, BK);
const pid = st.json?.id;
check("p02_start_by_message", st.status === 201 && !!pid, `старт сообщением bemIntake: ${st.status}`);

for (const el of ["n2", "n3", "n4", "n6"]) {
  await waitFor(async () => (await acts(pid)).includes(el), `${el} активен`);
  await step("kernel", pid, el);
}
const subs = await waitFor(async () => { const s = await procInstances({ superProcessInstanceId: pid }); return s.length === 3 ? s : null; }, "3 подпроцесса") ?? [];
const subVars = {};
for (const s of subs) {
  const v = (await api("GET", `/service/runtime/process-instances/${s.id}/variables`)).json ?? [];
  subVars[s.id] = Object.fromEntries(v.filter((x) => ["provider", "subIndex"].includes(x.name)).map((x) => [x.name, x.value]));
}
const split = ["anthropic", "openai", "anthropic"];
const idx = Object.values(subVars).map((x) => x.subIndex).sort().join(",");
check("p14_n7_three_subprocesses", subs.length === 3 && idx === "0,1,2" && Object.values(subVars).every((x) => x.provider === split[x.subIndex]), { n: subs.length, subVars: Object.values(subVars) });

// п.3: темы exec-* — исполнитель видит только работу своего поставщика.
await waitFor(async () => { let n = 0; for (const s of subs) n += (await executions({ processInstanceId: s.id })).filter((e) => e.activityId === "s2").length; return n === 3; }, "s2 у всех трёх");
const aA = (await acquire("exec-anthropic", "w-anthropic", "PT60S")).json ?? [];
const aO = (await acquire("exec-openai", "w-openai", "PT60S")).json ?? [];
const aA2 = (await acquire("exec-anthropic", "w-anthropic", "PT60S")).json ?? [];
check("p03_topics_by_provider", aA.length === 2 && aO.length === 1 && aA2.length === 0
  && aA.every((j) => subVars[j.processInstanceId]?.provider === "anthropic") && aO.every((j) => subVars[j.processInstanceId]?.provider === "openai"),
  { anthropic: aA.length, openai: aO.length, anthropicAgain: aA2.length });
const firstJob = aA[0];
for (const j of aA) log("  complete", j.elementId, (await completeJob(j.id, "w-anthropic")).status);
for (const j of aO) log("  complete", j.elementId, (await completeJob(j.id, "w-openai")).status);

// п.9: повторный complete того же job после успеха.
if (firstJob) {
  const again = await completeJob(firstJob.id, "w-anthropic");
  check("p09_repeat_complete_rejected", again.status === 404, `повторный complete: ${again.status} ${again.text.slice(0, 100)}`);
} else check("p09_repeat_complete_rejected", false, "нет работы для пробы");

// п.14: подтверждение subtaskAck одному экземпляру не двигает соседей.
await waitFor(async () => { let n = 0; for (const s of subs) n += (await executions({ processInstanceId: s.id })).filter((e) => e.activityId === "s3").length; return n === 3; }, "все подпроцессы в s3");
const waitAck = [];
for (const s of subs) waitAck.push({ sub: s.id, ex: (await executions({ processInstanceId: s.id })).find((e) => e.activityId === "s3")?.id });
const m1 = await api("PUT", `/service/runtime/executions/${waitAck[0].ex}`, { action: "messageEventReceived", messageName: "subtaskAck" });
await sleep(3000);
const left = [];
for (const w of waitAck) left.push((await procInstances({ id: w.sub })).length ? "жив" : "завершён");
check("p14_ack_one_only", m1.status < 300 && left.join(",") === "завершён,жив,жив" && !(await acts(pid)).includes("n8"), { ack: m1.status, left });
for (const w of waitAck.slice(1)) await api("PUT", `/service/runtime/executions/${w.ex}`, { action: "messageEventReceived", messageName: "subtaskAck" });
check("p14_all_acks_to_n8", !!(await waitFor(async () => (await acts(pid)).includes("n8"), "n8 после всех ack")), "после всех подтверждений — n8");

await step("kernel", pid, "n8");
await waitFor(async () => (await acts(pid)).includes("n9"), "n9");
await step("kernel", pid, "n9");
const split10 = await waitFor(async () => { const a = await acts(pid); return a.includes("n11") && a.includes("n12") ? a : null; }, "n11 и n12");
check("p14_n10_two_branches", !!split10, { acts: split10 });
await step("kernel-check", pid, "n11");
await waitFor(async () => !(await acts(pid)).includes("n11"), "n11 ушёл");
await sleep(3000);
const afterN11 = await acts(pid);
check("p14_n13_waits_both", afterN11.includes("n12") && !afterN11.includes("n14"), { afterN11 });
await step("kernel-publish", pid, "n12");
check("p14_n13_joins", !!(await waitFor(async () => (await acts(pid)).includes("n14"), "n14")), "после n12 — n14");
await step("kernel-assign", pid, "n14");
await waitFor(async () => (await acts(pid)).includes("n15"), "n15");

// п.4: n15 двигает только trigger.
for (const t of ["kernel", "kernel-check", "kernel-publish", "kernel-assign", "egress", "exec-anthropic", "exec-openai"]) {
  const js = (await acquire(t, "drain-w")).json ?? [];
  for (const j of js) log(`  drain ${t}: ${j.elementId}${j.processInstanceId === pid ? "" : "(чужой)"}`);
}
const n15ex = (await executions({ processInstanceId: pid, activityId: "n15" }))[0];
const msgTry = await api("PUT", `/service/runtime/executions/${n15ex?.id}`, { action: "messageEventReceived", messageName: "subtaskAck" });
await sleep(5000);
const still = await acts(pid);
check("p04_n15_not_moved_by_drain_or_message", msgTry.status >= 400 && still.includes("n15"), { message: msgTry.status, acts: still });
const tr = await api("PUT", `/service/runtime/executions/${n15ex?.id}`, { action: "trigger", variables: vars({ verdict: "ACCEPT" }) });
const toN17 = await waitFor(async () => (await acts(pid)).includes("n17"), "n17");
check("p04_n15_moved_by_trigger", tr.status === 200 && !!toN17, `trigger ${tr.status}`);
await step("kernel", pid, "n17");
await waitFor(async () => (await acts(pid)).includes("n18"), "n18");
await step("egress", pid, "n18");
const ended = await waitFor(async () => (await procInstances({ id: pid })).length === 0, "конец процесса");
check("p02_process_completed", !!ended, "процесс W-CI-2 завершён");

// п.6: история завершённого экземпляра — время есть, автора перехода нет.
const hp = (await api("GET", `/service/history/historic-process-instances?processInstanceId=${pid}`)).json?.data?.[0];
const ha = await history(pid);
const withTime = ha.filter((a) => a.startTime && a.endTime).length;
const withAssignee = ha.filter((a) => a.assignee).length;
check("p06_history_times", ha.length > 0 && withTime === ha.length && !!hp?.endTime, { rows: ha.length, withTime, end: hp?.endTime });
check("p06_no_transition_author_R47_finding", withAssignee === 0 && hp?.startUserId === process.env.ENGINE_USER, { withAssignee, startUserIsRestUser: hp?.startUserId === process.env.ENGINE_USER });
log("p02 пройдено узлов:", ha.map((x) => x.activityId).join(" "));
log("=== p02/p14 end");
