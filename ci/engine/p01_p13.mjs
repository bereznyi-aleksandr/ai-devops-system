// ДОКУМЕНТ: ci/engine/p01_p13.mjs
// ВЕРСИЯ: v1.0
// СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 06:15 +03:00
// ИСПОЛНИТЕЛЬ: Claude (сессия f19e07a7-6edd-48a5-9ede-88086c949326)
// НАЗНАЧЕНИЕ: п.1 и п.13 раздела 22 на PostgreSQL (перенос R47 p01_p13 v1.1 и p13b_kr511 v1.0, проверки с ожидаемым итогом):
//   движок жив, версия 8.0.0, лицензия Apache 2.0; граф раздела 12 — свой проверщик инвариантов 12.3 (с правилом
//   «из n7 ровно один поток, прямо в n8») и валидатор Flowable на четырёх испорченных копиях.
// ОЖИДАЕМО (как в R47): наш проверщик отклоняет все четыре копии; Flowable принимает их (201) — находка R47 повторяется.
import { readFileSync } from "node:fs";
import { S, api, deploy, log, setLog, check } from "./lib.mjs";

setLog(`${S}/p01_p13.log`);
log("=== p01/p13", new Date().toISOString());

const h = await api("GET", "/actuator/health");
check("p01_health", h.status === 200 && /UP/.test(h.text), `health ${h.status} ${h.text.slice(0, 80)}`);
const eng = await api("GET", "/service/management/engine");
check("p01_engine_version", eng.status === 200 && String(eng.json?.version).startsWith("8.0.0"), `engine ${eng.status} ${eng.json?.name} ${eng.json?.version}`);
const lic = readFileSync(`${S}/license.txt`, "utf8");
check("p01_license_apache2", /Apache License/.test(lic) && /Version 2\.0/.test(lic), lic.split(/\r?\n/).map((x) => x.trim()).filter(Boolean).slice(0, 2).join(" | "));

function graphCheck(xml, procId) {
  const body = xml.split(`<process id="${procId}"`)[1].split("</process>")[0];
  const nodes = {};
  for (const m of body.matchAll(/<(startEvent|serviceTask|callActivity|exclusiveGateway|parallelGateway|receiveTask|userTask|endEvent)\s+id="([^"]+)"([^>]*?)(?:\/>|>[\s\S]*?<\/\1>)/g)) nodes[m[2]] = { type: m[1], text: m[0] };
  const flows = [...body.matchAll(/<sequenceFlow id="([^"]+)" sourceRef="([^"]+)" targetRef="([^"]+)"/g)].map((m) => ({ id: m[1], s: m[2], t: m[3] }));
  const inn = (n) => flows.filter((f) => f.t === n).length, out = (n) => flows.filter((f) => f.s === n).length;
  const reach = (from) => { const seen = new Set([from]); const st = [from]; while (st.length) { const x = st.pop(); for (const f of flows) if (f.s === x && !seen.has(f.t)) { seen.add(f.t); st.push(f.t); } } return seen; };
  const errs = [];
  if (!(inn("n10") === 1 && out("n10") === 2)) errs.push(`n10 ${inn("n10")}/${out("n10")}`);
  if (!(inn("n13") === 2 && out("n13") === 1)) errs.push(`n13 вход/выход ${inn("n13")}/${out("n13")} (надо 2/1)`);
  for (const [id, n] of Object.entries(nodes)) if (n.type === "endEvent" && out(id) !== 0) errs.push(`${id} End Event с исходящим`);
  const n7o = flows.filter((f) => f.s === "n7");
  if (!(n7o.length === 1 && n7o[0].t === "n8")) errs.push(`n7 -> ${n7o.map((f) => f.t)} (надо прямо n8)`);
  if (!/isSequential="false"/.test(nodes.n7?.text ?? "") || /completionCondition/.test(nodes.n7?.text ?? "")) errs.push("n7 не параллельный или с completionCondition");
  const r1 = reach("n1"); for (const id of Object.keys(nodes)) if (!r1.has(id)) errs.push(`${id} недостижим`);
  for (const [a, ts] of [["n17", ["n18", "n20"]], ["n16", ["n17", "n20"]]]) { const r = reach(a); for (const t of ts) if (!r.has(t)) errs.push(`из ${a} недостижим ${t}`); }
  return { nodes: Object.keys(nodes).length, flows: flows.length, errs };
}

const base = readFileSync(new URL("./bem_work.bpmn20.xml", import.meta.url), "utf8");
const c0 = graphCheck(base, "bem_work");
check("p13_own_checker_base", c0.nodes === 20 && c0.flows === 24 && c0.errs.length === 0, c0);
const d0 = await deploy("bem_work.bpmn20.xml", base);
check("p13_deploy_base", d0.status === 201, `deploy ${d0.status}`);

const mk = (tag, f) => f(base).replace('id="bem_work"', `id="bem_work_${tag}"`).replace('name="bemIntake"', `name="bemIntake_${tag}"`)
  .replace('name="subtaskAck"', `name="subtaskAck_${tag}"`).replace('id="bem_subtask"', `id="bem_subtask_${tag}"`);
const bad = {
  n20out: (x) => x.replace('<sequenceFlow id="f24"', '<sequenceFlow id="fX1" sourceRef="n20" targetRef="n6"/>\n    <sequenceFlow id="f24"'),
  orphanNode: (x) => x.replace('<endEvent id="n20"', '<serviceTask id="n99" name="99 Сирота" flowable:type="external-worker" flowable:topic="kernel"/>\n    <endEvent id="n20"')
    .replace('<sequenceFlow id="f24"', '<sequenceFlow id="fX2" sourceRef="n99" targetRef="n20"/>\n    <sequenceFlow id="f24"'),
  joinAfter7: (x) => x.replace('<serviceTask id="n8"', '<parallelGateway id="n7j" name="лишнее слияние"/>\n    <serviceTask id="n8"')
    .replace('<sequenceFlow id="f08" sourceRef="n7" targetRef="n8"/>', '<sequenceFlow id="f08" sourceRef="n7" targetRef="n7j"/>\n    <sequenceFlow id="f08b" sourceRef="n7j" targetRef="n8"/>'),
  n13oneIn: (x) => x.replace('<sequenceFlow id="f14" sourceRef="n12" targetRef="n13"/>', '<sequenceFlow id="f14" sourceRef="n12" targetRef="n14"/>'),
};
for (const [tag, f] of Object.entries(bad)) {
  const xml = mk(`neg_${tag}`, f);
  check(`p13_mutation_applied_${tag}`, xml !== mk(`neg_${tag}`, (x) => x), "испорченная копия отличается от исходной");
  const c = graphCheck(xml, `bem_work_neg_${tag}`);
  check(`p13_own_checker_rejects_${tag}`, c.errs.length > 0, c.errs.join("; "));
  const d = await deploy(`bem_work_neg_${tag}.bpmn20.xml`, xml);
  check(`p13_flowable_accepts_${tag}_R47_finding`, d.status === 201, `Flowable ${d.status}${d.status >= 400 ? " " + d.text.slice(0, 120) : " принял"}`);
}
log("=== p01/p13 end");
