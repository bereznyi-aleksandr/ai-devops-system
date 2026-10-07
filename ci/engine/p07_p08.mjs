// ДОКУМЕНТ: ci/engine/p07_p08.mjs
// ВЕРСИЯ: v1.1 (v1.1, R51, ответ на M-R50-01 и M-R50-02 ChatGPT: эффект п.7 пишется в отдельную базу bem_probe_ci и
//   читается оттуда, плюс мутация «наивный адаптер» обязана дать FAIL; п.8 — правило поставщиков проверяется отдельно от
//   самоавторства, плюс мутация «правило компаний удалено» обязана дать FAIL; живой отказ на n14 назван заглушкой)
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 06:25 +03:00
// ДАТА ОБНОВЛЕНИЯ: 2026-10-07 07:25 +03:00 (сессия f19e07a7-6edd-48a5-9ede-88086c949326)
// ИСПОЛНИТЕЛЬ: Claude (сессия f19e07a7-6edd-48a5-9ede-88086c949326)
// НАЗНАЧЕНИЕ: пункты 7 и 8 раздела 22 на PostgreSQL (перенос R47 p03_p07_p08 v1.0 и p07d v1.0, с ожидаемым итогом):
//   п.8 — маршрутизатор-заглушка Kernel по матрице 9.4: автор не назначается проверяющим; в строках 1–2 проверяющий
//   из другой компании, в строке 4 — по одному от двух компаний. Каждое правило проверяется своим отрицательным случаем.
//   Живой отказ на n14 делает ЛОКАЛЬНАЯ заглушка; серверный отказ назначения (Kernel/БД) этой пробой НЕ проверяется.
//   п.7 — аренда истекла, а вызов ещё идёт: B получает ту же работу; оба вызывают адаптер эффекта с ключом работы;
//   эффект — строка в отдельной базе bem_probe_ci (не в памяти пробы); поздний complete A отклонён. Дважды.
import { execFileSync } from "node:child_process";
import { api, log, setLog, check, S, startByMessage, acquire, completeJob, executions, procInstances, sleep, waitFor, acts, pvars } from "./lib.mjs";

setLog(`${S}/p07_p08.log`);
log("=== p07/p08", new Date().toISOString());

const POOL = [
  { id: "claude-1", company: "anthropic" }, { id: "claude-2", company: "anthropic" },
  { id: "gpt-1", company: "openai" }, { id: "gpt-2", company: "openai" },
  { id: "human-op", company: "human", human: true }, { id: "human-2", company: "human", human: true },
  { id: "claude-3", company: "anthropic" },
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
// Три правила — три кода отказа; companyRules=false — мутация «правило компаний удалено».
function checkAssignment(authors, reviewers, row, { companyRules = true } = {}) {
  if (reviewers.some((r) => !r)) return "ОТКАЗ:MISSING";
  const aIds = new Set(authors.map((a) => a.id));
  if (reviewers.some((r) => aIds.has(r.id))) return "ОТКАЗ:AUTHOR";
  if (!companyRules) return "OK";
  const aCos = new Set(authors.filter((a) => !a.human).map((a) => a.company));
  if ((row === 1 || row === 2) && reviewers.some((r) => aCos.has(r.company))) return "ОТКАЗ:SAME_PROVIDER";
  if (row === 4 && new Set(reviewers.map((r) => r.company)).size < 2) return "ОТКАЗ:ONE_PROVIDER";
  return "OK";
}
const cases = [[[POOL[0]], "NORMAL"], [[POOL[0]], "CRITICAL"], [[POOL[0], POOL[2]], "NORMAL"], [[POOL[0], POOL[2]], "CRITICAL"], [[POOL[4]], "NORMAL"]];
const rows = cases.map(([a, c]) => { const r = route(a, c); return { row: r.row, ok: checkAssignment(a, r.reviewers, r.row), rv: r.reviewers.map((x) => x?.id) }; });
check("p08_matrix_rows_1_5", rows.map((r) => r.row).join(",") === "1,2,3,4,5" && rows.every((r) => r.ok === "OK"), rows);
const self = checkAssignment([POOL[0]], [POOL[0]], 1);
check("p08_author_self_assign_refused", self === "ОТКАЗ:AUTHOR", self);
// Строка 4: оба проверяющих НЕ авторы, но из одной компании — отказ даёт только правило поставщиков.
const A4 = [POOL[0], POOL[2]], R4 = [POOL[1], POOL[6]];
const nonAuthors4 = R4.every((r) => !A4.some((a) => a.id === r.id));
const row4 = checkAssignment(A4, R4, 4);
check("p08_row4_one_provider_refused", nonAuthors4 && row4 === "ОТКАЗ:ONE_PROVIDER", { authors: A4.map((x) => x.id), reviewers: R4.map((x) => x.id), nonAuthors: nonAuthors4, result: row4 });
// Строка 1: проверяющий не автор, но из компании автора.
const A1 = [POOL[0]], R1 = [POOL[1]];
const row1 = checkAssignment(A1, R1, 1);
check("p08_row1_same_provider_refused", row1 === "ОТКАЗ:SAME_PROVIDER", { authors: A1.map((x) => x.id), reviewers: R1.map((x) => x.id), result: row1 });
// Мутация: без правила компаний оба отрицательных случая проходят — значит, проверки выше на поломку чувствительны.
const m4 = checkAssignment(A4, R4, 4, { companyRules: false }), m1 = checkAssignment(A1, R1, 1, { companyRules: false });
check("p08_mutation_company_rule_removed_gives_fail", m4 === "OK" && m1 === "OK" && row4 !== m4 && row1 !== m1,
  { mutated: { row4: m4, row1: m1 }, real: { row4, row1 }, meaning: "без правила компаний p08_row4/p08_row1 дали бы FAIL" });

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
  const bad = checkAssignment(authors, [POOL[0]], 1);
  check("p08_live_stub_refuses_author_n14_open", bad === "ОТКАЗ:AUTHOR" && jobs14.length > 0 && (await acts(pid)).includes("n14"),
    `${bad}; отказ сделала локальная заглушка, назначение серверу не отправлялось; работа n14 получена и не завершена; серверный отказ не проверяется`);
  const good = route(authors, v.criticality);
  const goodCheck = checkAssignment(authors, good.reviewers, good.row);
  const c14 = await completeJob(jobs14[0]?.id, "router", { reviewersJson: JSON.stringify(good.reviewers.map((x) => x.id)) });
  const atN15 = await waitFor(async () => (await acts(pid)).includes("n15"), "n15");
  check("p08_live_route_row1_to_n15", good.row === 1 && goodCheck === "OK" && good.reviewers[0]?.id === "gpt-1" && c14.status < 300 && !!atN15, { row: good.row, check: goodCheck, reviewers: good.reviewers.map((x) => x.id), complete: c14.status });
}

// п.7: аренда PT5S, A держит 8 с; B получает ту же работу; эффект один; поздний complete A отклонён. Дважды.
// Внешняя система — отдельная база bem_probe_ci (создаёт ci/engine_pg_probes.sh). Каждый вызов адаптера пишет попытку
// в attempts; эффект — строка effects с уникальным ключом работы. Мутация: наивный адаптер без ключа пишет в effects_naive.
const psql = (sql) => execFileSync("psql", ["-X", "-v", "ON_ERROR_STOP=1", "-d", "bem_probe_ci", "-Atc", sql], { encoding: "utf8" }).trim();
const q = (s) => "'" + String(s).replace(/'/g, "''") + "'";
psql("CREATE TABLE IF NOT EXISTS attempts (work_key text NOT NULL, worker text NOT NULL, at timestamptz NOT NULL DEFAULT clock_timestamp());" +
  "CREATE TABLE IF NOT EXISTS effects (work_key text PRIMARY KEY, worker text NOT NULL, at timestamptz NOT NULL DEFAULT clock_timestamp());" +
  "CREATE TABLE IF NOT EXISTS effects_naive (work_key text NOT NULL, worker text NOT NULL, at timestamptz NOT NULL DEFAULT clock_timestamp());");
const jobKey = (j) => `${j.processInstanceId}|${j.elementId}|${j.id}`;
const adapter = (j, w) => psql(`INSERT INTO attempts(work_key, worker) VALUES (${q(jobKey(j))}, ${q(w)});` +
  `INSERT INTO effects(work_key, worker) VALUES (${q(jobKey(j))}, ${q(w)}) ON CONFLICT (work_key) DO NOTHING;`);
const naiveAdapter = (j, w) => psql(`INSERT INTO effects_naive(work_key, worker) VALUES (${q(jobKey(j))}, ${q(w)});`);
const readStore = (table, k) => { const [n, by] = psql(`SELECT count(*), coalesce(string_agg(worker, ',' ORDER BY at), '') FROM ${table} WHERE work_key = ${q(k)}`).split("|"); return { n: Number(n), by }; };
const oneEffectByA = (s) => s.n === 1 && s.by === "A";
for (const run of [1, 2]) {
  const bk = `W-CI-7-${run}`;
  const p = (await startByMessage("bemIntake", { subtaskCount: 1, providers: "anthropic", workKey: bk, authorsJson: "[]" }, bk)).json.id;
  await kernelUpTo(p, ["n2", "n3", "n4", "n6"]);
  const sp = (await waitFor(async () => { const q = await procInstances({ superProcessInstanceId: p }); return q.length ? q : null; }, "sub"))[0].id;
  let ja = [];
  for (let i = 0; i < 60 && !ja.length; i++) { ja = ((await acquire("exec-anthropic", "w-A", "PT5S")).json ?? []).filter((j) => j.processInstanceId === sp); if (!ja.length) await sleep(500); }
  const A = ja[0];
  if (A) { adapter(A, "A"); naiveAdapter(A, "A"); }
  const early = ((await acquire("exec-anthropic", "w-B", "PT60S")).json ?? []).filter((j) => j.processInstanceId === sp);
  await sleep(8000);
  const t0 = Date.now(); let B = null;
  while (!B && Date.now() - t0 < 180000) {
    B = ((await acquire("exec-anthropic", "w-B", "PT60S")).json ?? []).find((j) => j.processInstanceId === sp) ?? null;
    if (!B) await sleep(1000);
  }
  const waitedS = Math.round((Date.now() - t0) / 1000);
  if (B) { adapter(B, "B"); naiveAdapter(B, "B"); }
  const k = A ? jobKey(A) : "нет";
  const att = readStore("attempts", k), eff = readStore("effects", k), naive = readStore("effects_naive", k);
  const cb = B ? await completeJob(B.id, "w-B") : { status: 0, text: "" };
  const ca = await completeJob(A?.id, "w-A");
  const s3 = await waitFor(async () => (await executions({ processInstanceId: sp })).find((e) => e.activityId === "s3"), "s3");
  check(`p07_run${run}_lease_expiry_one_effect`, !!A && early.length === 0 && B?.id === A?.id && !!B && jobKey(B) === k && att.n === 2 && oneEffectByA(eff) && cb.status === 204 && ca.status >= 400 && !!s3,
    { early: early.length, sameJob: B?.id === A?.id, waitedS, key: k, attempts: att, effects: eff, completeB: cb.status, lateCompleteA: ca.status, lateText: ca.text.slice(0, 100), s3: !!s3 });
  // Мутация: тот же повтор через наивный адаптер даёт два эффекта — критерий oneEffectByA обязан его отвергнуть.
  check(`p07_run${run}_mutation_naive_adapter_gives_fail`, naive.n === 2 && !oneEffectByA(naive) && oneEffectByA(eff), { naive, real: eff, meaning: "без ключа работы p07 дал бы FAIL" });
}
log("=== p07/p08 end");
