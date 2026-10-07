// ДОКУМЕНТ: ci/engine/p07_p08.mjs
// ВЕРСИЯ: v1.0
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 06:25 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия f19e07a7-6edd-48a5-9ede-88086c949326)
// НАЗНАЧЕНИЕ: пункты 7 и 8 раздела 22 на PostgreSQL (перенос R47 p03_p07_p08 v1.0 и p07d v1.0, с ожидаемым итогом):
//   п.8 — маршрутизатор-заглушка Kernel по матрице 9.4 не назначает автора проверяющим (таблично и вживую на n14);
//   п.7 — аренда истекла, а вызов ещё идёт: B получает ту же работу, эффект один, поздний complete A отклонён. Дважды.
import { api, log, setLog, check, S, startByMessage, acquire, completeJob, executions, procInstances, sleep, waitFor, acts, pvars } from "./lib.mjs";

setLog(`${S}/p07_p08.log`);
log("=== p07/p08", new Date().toISOString());

const POOL = [
  { id: "claude-1", company: "anthropic" }, { id: "claude-2", company: "anthropic" },
  { id: "gpt-1", company: "openai" }, { id: "gpt-2", company: "openai" },
  { id: "human-op", company: "human", human: true }, { id: "human-2", company: "human", human: true },
];
function route(authors, criticality) {
  const aIds = new Set(authors.map((a) => a.id));
  const aCos = new Set(authors.filter((a) => !a.human).map((a) => a.company));
  const free = POOL.filter((p) => !aIds.has(p.id));
  if (authors.some((a) => a.human)) return { row: 5, reviewers: [free.find((p) => !p.human) ?? free[0]] };
  if (aCos.size === 1) {
    const other = free.find((p) => !p.human && !aCos.has(p.company));
    return { row: criticality === "CRITICAL" ? 2 : 1, reviewers: [other] };
  }
  if (criticality !== "CRITICAL") return { row: 3, reviewers: [free.find((p) => !p.human)] };
  return { row: 4, reviewers: ["anthropic", "openai"].map((c) => free.find((p) => p.company === c)) };
}
function checkAssignment(authors, reviewers) {
  const aIds = new Set(authors.map((a) => a.id));
  const bad = reviewers.filter((r) => !r || aIds.has(r.id));
  return bad.length ? `ОТКАЗ (${bad.map((r) => r?.id ?? "нет").join(",")})` : "OK";
}
const cases = [[[POOL[0]], "NORMAL"], [[POOL[0]], "CRITICAL"], [[POOL[0], POOL[2]], "NORMAL"], [[POOL[0], POOL[2]], "CRITICAL"], [[POOL[4]], "NORMAL"]];
const rows = cases.map(([a, c]) => { const r = route(a, c); return { row: r.row, ok: checkAssignment(a, r.reviewers), rv: r.reviewers.map((x) => x?.id) }; });
check("p08_matrix_rows_1_5", rows.map((r) => r.row).join(",") === "1,2,3,4,5" && rows.every((r) => r.ok === "OK"), rows);
check("p08_author_self_assign_refused", checkAssignment([POOL[0]], [POOL[0]]).startsWith("ОТКАЗ"), checkAssignment([POOL[0]], [POOL[0]]));
const row4Same = (() => { const rv = [POOL[0], POOL[1]]; return checkAssignment([POOL[0], POOL[2]], rv) !== "OK" || new Set(rv.map((x) => x.company)).size < 2 ? "ОТКАЗ" : "OK"; })();
check("p08_row4_one_provider_refused", row4Same === "ОТКАЗ", row4Same);

const kvars = (el) => (el === "n4" ? { criticality: "NORMAL" } : {});
async function kernelUpTo(pid, els) {
  for (const el of els) {
    await waitFor(async () => (await acts(pid)).includes(el), el);
    for (let i = 0; i < 40; i++) {
      const js = (await acquire("kernel", "kernel-w")).json ?? [];
      for (const x of js) await completeJob(x.id, "kernel-w", kvars(x.elementId));
      if (js.some((x) => x.processInstanceId === pid && x.elementId === el)) break;
      await sleep(500);
    }
  }
}
async function topicOnce(topic, pid) {
  for (let i = 0; i < 40; i++) {
    const js = (await acquire(topic, "kernel-w")).json ?? [];
    for (const x of js) await completeJob(x.id, "kernel-w");
    if (js.some((x) => x.processInstanceId === pid)) return true;
    await sleep(500);
  }
  return false;
}

// п.8 вживую: одна подзадача anthropic, автор claude-1; маршрутизатор на n14.
{
  const BK = "W-CI-8";
  const pid = (await startByMessage("bemIntake", { subtaskCount: 1, providers: "anthropic", workKey: BK, authorsJson: JSON.stringify([POOL[0]]) }, BK)).json.id;
  await kernelUpTo(pid, ["n2", "n3", "n4", "n6"]);
  const sp = (await waitFor(async () => { const q = await procInstances({ superProcessInstanceId: pid }); return q.length ? q : null; }, "sub"))[0].id;
  let j = [];
  for (let i = 0; i < 60 && !j.length; i++) { j = ((await acquire("exec-anthropic", "w-anthropic", "PT60S")).json ?? []).filter((x) => x.processInstanceId === sp); if (!j.length) await sleep(500); }
  for (const x of j) await completeJob(x.id, "w-anthropic");
  const ex = await waitFor(async () => (await executions({ processInstanceId: sp })).find((e) => e.activityId === "s3"), "s3");
  await api("PUT", `/service/runtime/executions/${ex?.id}`, { action: "messageEventReceived", messageName: "subtaskAck" });
  await kernelUpTo(pid, ["n8", "n9"]);
  await topicOnce("kernel-check", pid); await topicOnce("kernel-publish", pid);
  await waitFor(async () => (await acts(pid)).includes("n14"), "n14");
  let jobs14 = [];
  for (let i = 0; i < 40 && !jobs14.length; i++) { jobs14 = ((await acquire("kernel-assign", "router", "PT60S")).json ?? []).filter((x) => x.processInstanceId === pid); if (!jobs14.length) await sleep(500); }
  const v = await pvars(pid);
  const authors = JSON.parse(v.authorsJson);
  const bad = checkAssignment(authors, [POOL[0]]);
  check("p08_live_author_refused_at_n14", bad.startsWith("ОТКАЗ") && (await acts(pid)).includes("n14"), `${bad}; работа n14 не завершена`);
  const good = route(authors, v.criticality);
  const c14 = await completeJob(jobs14[0]?.id, "router", { reviewersJson: JSON.stringify(good.reviewers.map((x) => x.id)) });
  const atN15 = await waitFor(async () => (await acts(pid)).includes("n15"), "n15");
  check("p08_live_route_row1_to_n15", good.row === 1 && good.reviewers[0]?.id === "gpt-1" && c14.status < 300 && !!atN15, { row: good.row, reviewers: good.reviewers.map((x) => x.id), complete: c14.status });
}

// п.7: аренда PT5S, A держит 8 с; B получает ту же работу; эффект один; поздний complete A отклонён. Дважды.
for (const run of [1, 2]) {
  const bk = `W-CI-7-${run}`;
  const p = (await startByMessage("bemIntake", { subtaskCount: 1, providers: "anthropic", workKey: bk, authorsJson: "[]" }, bk)).json.id;
  await kernelUpTo(p, ["n2", "n3", "n4", "n6"]);
  const sp = (await waitFor(async () => { const q = await procInstances({ superProcessInstanceId: p }); return q.length ? q : null; }, "sub"))[0].id;
  let ja = [];
  for (let i = 0; i < 60 && !ja.length; i++) { ja = ((await acquire("exec-anthropic", "w-A", "PT5S")).json ?? []).filter((j) => j.processInstanceId === sp); if (!ja.length) await sleep(500); }
  const A = ja[0];
  const eff = new Map(); const ad = (k, w) => { if (!eff.has(k)) eff.set(k, w); return eff.get(k); };
  const k = `${sp}|s2|0`;
  ad(k, "A");
  const early = ((await acquire("exec-anthropic", "w-B", "PT60S")).json ?? []).filter((j) => j.processInstanceId === sp);
  await sleep(8000);
  const t0 = Date.now(); let B = null;
  while (!B && Date.now() - t0 < 180000) {
    B = ((await acquire("exec-anthropic", "w-B", "PT60S")).json ?? []).find((j) => j.processInstanceId === sp) ?? null;
    if (!B) await sleep(1000);
  }
  const waitedS = Math.round((Date.now() - t0) / 1000);
  const by = B ? ad(k, "B") : null;
  const cb = B ? await completeJob(B.id, "w-B") : { status: 0, text: "" };
  const ca = await completeJob(A?.id, "w-A");
  const s3 = await waitFor(async () => (await executions({ processInstanceId: sp })).find((e) => e.activityId === "s3"), "s3");
  check(`p07_run${run}_lease_expiry_one_effect`, !!A && early.length === 0 && B?.id === A?.id && by === "A" && eff.size === 1 && cb.status === 204 && ca.status >= 400 && !!s3,
    { early: early.length, sameJob: B?.id === A?.id, waitedS, effectBy: by, effects: eff.size, completeB: cb.status, lateCompleteA: ca.status, lateText: ca.text.slice(0, 100), s3: !!s3 });
}
log("=== p07/p08 end");
